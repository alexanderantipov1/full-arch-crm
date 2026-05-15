import { zodToJsonSchema } from "zod-to-json-schema";
import { anthropic, hasSignedAnthropicBaa } from "../services/ai";
import { storage } from "../storage";
import { listTools } from "../tools/registry";
import { runTool } from "../tools/runner";
import type { Tool, ToolContext } from "../tools/types";
import type {
  AgentLoopInput,
  WorkflowOptions,
  WorkflowResult,
  WorkflowStep,
} from "./types";

// Agent loop wired to Anthropic's native tool-use. The model decides which
// tool to call; we execute it; we feed the result back. Repeat until the
// model returns a final text answer, or we hit a safety cap.
//
// This is the seam where future durability lives (per fusion_crm's
// `workflow` schema): today we hold steps in memory and return them in the
// result; later they get persisted to `workflow.instance` + `workflow.step`
// so a crashed run can resume.

const DEFAULT_MAX_ITERATIONS = 8;
const DEFAULT_TIMEOUT_MS = 60_000;
const DEFAULT_SYSTEM_PROMPT = `You are an operations agent for an AI-native dental implant clinic. You complete tasks by calling tools. Prefer the most direct path to the goal. When the goal is achieved, respond with a concise summary of what you did and the result. Do not invent tool calls; only call tools that are available.`;

// Convert our Tool<I,O> shape to the Anthropic tools schema. We feed the
// model the same JSON schemas that the MCP surface uses, so the model "sees"
// the same contract whether it's calling via MCP or via the agent loop.
function toAnthropicTool(tool: Tool<any, any>) {
  return {
    name: tool.name,
    description: tool.description,
    input_schema: zodToJsonSchema(tool.inputSchema, { target: "openApi3" }) as any,
  };
}

// Detect "the model wants to call a tool" in an Anthropic response.
function findToolUseBlocks(content: any[]): Array<{
  id: string;
  name: string;
  input: Record<string, unknown>;
}> {
  return content
    .filter((b) => b?.type === "tool_use")
    .map((b) => ({ id: b.id, name: b.name, input: b.input ?? {} }));
}

function extractTextSummary(content: any[]): string {
  return content
    .filter((b) => b?.type === "text")
    .map((b) => b.text)
    .join("\n")
    .trim();
}

export async function runAgentLoop({ ctx, goal, opts }: AgentLoopInput): Promise<WorkflowResult> {
  const maxIterations = opts?.maxIterations ?? DEFAULT_MAX_ITERATIONS;
  const timeoutMs = opts?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const systemPrompt = opts?.systemPrompt ?? DEFAULT_SYSTEM_PROMPT;
  const allowedTools = opts?.tools ?? listTools();

  const tools = allowedTools.map(toAnthropicTool);
  const toolByName = new Map(allowedTools.map((t) => [t.name, t]));

  // Persist a `workflow_instance` row up front in status='running' so the
  // operator UI can see in-flight runs. If persistence fails (DB down,
  // etc.) we log but keep going — the loop still works in-memory; we just
  // lose durability for this one run.
  let instanceId: string | null = null;
  try {
    const instance = await storage.createWorkflowInstance({
      principalUserId: ctx.principal.userId,
      principalEmail: ctx.principal.email ?? null,
      goal,
      status: "running",
      endReason: null,
      finalAnswer: null,
      errorMessage: null,
      iterationsUsed: 0,
      allowedToolNames: allowedTools.map((t) => t.name),
    } as any);
    instanceId = instance.id;
  } catch (err) {
    console.error("workflow: failed to create instance row, continuing in-memory only:", err);
  }

  // Anthropic API message history. Grows by one assistant turn + one user
  // turn (containing tool results) per iteration.
  const messages: Array<{ role: "user" | "assistant"; content: any }> = [
    { role: "user", content: goal },
  ];

  const steps: WorkflowStep[] = [];
  const startTime = Date.now();
  let iteration = 0;
  let finalAnswer = "";

  // Helper: write the final status to the workflow_instance row. Never
  // lets a persistence failure mask the in-memory return — we surface the
  // result regardless and just log the storage error.
  async function finalize(
    status: "completed" | "failed" | "timeout" | "max_iterations",
    endReason: string,
    answer: string,
    errorMessage: string | null,
  ): Promise<WorkflowResult> {
    if (instanceId) {
      try {
        await storage.updateWorkflowInstance(instanceId, {
          status,
          endReason,
          finalAnswer: answer,
          errorMessage,
          iterationsUsed: iteration,
          completedAt: new Date(),
        } as any);
      } catch (err) {
        console.error("workflow: failed to finalize instance row:", err);
      }
    }
    return {
      goal,
      finalAnswer: answer,
      steps,
      endReason: status === "failed" ? "error" : status,
      totalDurationMs: Date.now() - startTime,
      iterations: iteration,
    };
  }

  // Helper: persist one step. Same fail-soft posture as instance writes.
  async function persistStep(step: WorkflowStep): Promise<void> {
    if (!instanceId) return;
    try {
      await storage.createWorkflowStep({
        instanceId,
        iteration: step.iteration,
        toolName: step.toolName,
        input: step.input as any,
        result: step.result as any,
        durationMs: step.durationMs,
      } as any);
    } catch (err) {
      console.error("workflow: failed to persist step:", err);
    }
  }

  while (iteration < maxIterations) {
    if (Date.now() - startTime > timeoutMs) {
      return finalize("timeout", "timeout", finalAnswer || "(agent timed out)", null);
    }

    iteration++;

    if (!hasSignedAnthropicBaa()) {
      return finalize(
        "failed",
        "error",
        "(agent failed: Anthropic BAA is not configured)",
        "Anthropic BAA is not configured; workflow agent prompts may include PHI.",
      );
    }

    let response;
    try {
      response = await anthropic.messages.create({
        model: "claude-opus-4-5",
        max_tokens: 4000,
        system: systemPrompt,
        tools,
        messages,
      });
    } catch (err: any) {
      console.error("Agent loop: Anthropic call failed:", err);
      return finalize(
        "failed",
        "error",
        "(agent failed: AI service unavailable)",
        err?.message ?? "Anthropic call failed",
      );
    }

    const content = response.content as any[];
    const toolUses = findToolUseBlocks(content);

    // If the model returned no tool_use blocks, it's done. Capture its text
    // as the final answer and exit.
    if (toolUses.length === 0) {
      finalAnswer = extractTextSummary(content);
      return finalize("completed", "completed", finalAnswer || "(no answer)", null);
    }

    // Add the assistant's tool-use turn to the history.
    messages.push({ role: "assistant", content });

    // Run each tool call sequentially. Anthropic supports parallel tool_use
    // blocks in one turn; we execute them in order for predictable audit
    // ordering. If we ever need real parallelism, this is the spot.
    const toolResultBlocks: any[] = [];
    for (const call of toolUses) {
      const tool = toolByName.get(call.name);
      const stepStart = Date.now();

      if (!tool) {
        const errorStep: WorkflowStep = {
          iteration,
          toolName: call.name,
          input: call.input,
          result: { ok: false, error: { code: "not_found", message: `Unknown tool: ${call.name}` } },
          durationMs: Date.now() - stepStart,
        };
        steps.push(errorStep);
        await persistStep(errorStep);
        toolResultBlocks.push({
          type: "tool_result",
          tool_use_id: call.id,
          is_error: true,
          content: `Unknown tool: ${call.name}`,
        });
        continue;
      }

      const result = await runTool(tool, ctx, call.input);
      const step: WorkflowStep = {
        iteration,
        toolName: call.name,
        input: call.input,
        result: result.ok ? { ok: true, data: result.data } : { ok: false, error: result.error },
        durationMs: Date.now() - stepStart,
      };
      steps.push(step);
      await persistStep(step);

      toolResultBlocks.push({
        type: "tool_result",
        tool_use_id: call.id,
        is_error: !result.ok,
        content: result.ok
          ? JSON.stringify(result.data)
          : `Tool error: ${result.error.code} — ${result.error.message}`,
      });
    }

    messages.push({ role: "user", content: toolResultBlocks });
  }

  // Iteration cap hit without the model finishing. Surface what we have.
  return finalize(
    "max_iterations",
    "max_iterations",
    finalAnswer || "(max iterations reached without final answer)",
    null,
  );
}

import { z } from "zod";
import { defineTool } from "../types";
import type { WorkflowResult } from "../../workflow/types";

// Note: runAgentLoop and listTools are both lazy-imported inside the handler.
// Static imports would create a cycle: registry → runWorkflow → runner →
// registry. Lazy imports break the cycle at module-load time and the values
// are only resolved when the tool actually runs.

// Exposes the agent loop AS A TOOL — meaning Claude Code (over MCP) and any
// other AI client can ask the CRM to run a multi-step workflow with the
// CRM's own tools. This is the recursive-AI seam: an outside model
// delegates work to an inside model that uses internal tools to fulfill it.

const inputSchema = z.object({
  goal: z.string().trim().min(1, "Goal is required"),
  maxIterations: z.number().int().positive().max(20).optional(),
  timeoutMs: z.number().int().positive().max(300_000).optional(),
  // Subset of tool names to make available to the workflow. Omit to expose
  // the full registry (minus this tool itself — see below).
  allowedToolNames: z.array(z.string()).optional(),
});

export type RunWorkflowInput = z.infer<typeof inputSchema>;
export type RunWorkflowOutput = WorkflowResult;

export const runWorkflowTool = defineTool<RunWorkflowInput, RunWorkflowOutput>({
  name: "workflow.run",
  description:
    "Run a multi-step AI agent loop to accomplish a goal using the CRM's available tools. Returns the final answer plus a full audit trail of every tool call made along the way.",
  inputSchema,
  async handler(ctx, input) {
    // Lazy-import to break the cycle described in the header.
    const { listTools } = await import("../registry");
    const { runAgentLoop } = await import("../../workflow/runner");

    let allowedTools = listTools().filter((t) => t.name !== "workflow.run");
    if (input.allowedToolNames && input.allowedToolNames.length > 0) {
      const allow = new Set(input.allowedToolNames);
      allowedTools = allowedTools.filter((t) => allow.has(t.name));
    }

    const result = await runAgentLoop({
      ctx,
      goal: input.goal,
      opts: {
        maxIterations: input.maxIterations,
        timeoutMs: input.timeoutMs,
        tools: allowedTools,
      },
    });

    return { ok: true, data: result };
  },
});

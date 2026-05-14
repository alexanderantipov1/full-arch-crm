import type { Tool, ToolContext, ToolError } from "../tools/types";

// A single iteration of the agent loop: model decided to call a tool, we ran
// it, here are the inputs and outputs. Persisted in the workflow result so
// the operator can see exactly what the agent did.

export interface WorkflowStep {
  iteration: number;
  toolName: string;
  input: unknown;
  result:
    | { ok: true; data: unknown }
    | { ok: false; error: ToolError };
  // Time spent on this step in ms; useful for debugging slow tools.
  durationMs: number;
}

export type WorkflowEndReason =
  | "completed" // Model returned a final answer without requesting another tool
  | "max_iterations" // Hit the iteration cap
  | "timeout" // Hit the wall-clock cap
  | "error"; // Anthropic call failed or another fatal error

export interface WorkflowResult {
  goal: string;
  finalAnswer: string;
  steps: WorkflowStep[];
  endReason: WorkflowEndReason;
  totalDurationMs: number;
  iterations: number;
}

export interface WorkflowOptions {
  // Maximum number of tool-use iterations before forcing the loop to stop.
  // Prevents runaway agents. Default: 8.
  maxIterations?: number;
  // Wall-clock timeout in ms. Default: 60_000.
  timeoutMs?: number;
  // Restrict which tools the agent can call. If omitted, the full registry
  // is exposed. Use this for least-privilege workflows.
  tools?: Array<Tool<any, any>>;
  // Optional system prompt prepended to the agent. If omitted, a default
  // dental-practice-operator prompt is used.
  systemPrompt?: string;
}

export interface AgentLoopInput {
  ctx: ToolContext;
  goal: string;
  opts?: WorkflowOptions;
}

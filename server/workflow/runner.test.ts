import { describe, it, expect, vi, beforeEach } from "vitest";
import { z } from "zod";

// Mock the AI service so we can script the Anthropic responses turn-by-turn.
const anthropicMock = vi.hoisted(() => ({
  messages: { create: vi.fn() },
}));
vi.mock("../services/ai", () => ({
  anthropic: anthropicMock,
  askClaude: vi.fn(),
}));

// Mock the storage so persistence is observable without a real DB. Each
// fake method is a spy so tests can assert what got written. createWorkflowInstance
// returns a fixed id; the rest are no-op resolvers.
const storageMock = vi.hoisted(() => ({
  createWorkflowInstance: vi.fn(async (data: any) => ({ id: "wf-test-1", ...data })),
  updateWorkflowInstance: vi.fn().mockResolvedValue(undefined),
  createWorkflowStep: vi.fn().mockResolvedValue(undefined),
  getWorkflowInstance: vi.fn(),
  listWorkflowInstances: vi.fn(),
  getWorkflowSteps: vi.fn(),
}));
vi.mock("../storage", () => ({ storage: storageMock }));

import { runAgentLoop } from "./runner";

// Build a small set of fake tools after imports — passed to runAgentLoop via
// `opts.tools` in every test so the real registry is never touched. Avoids
// the circular `runner → registry → runWorkflow → runner` chain and keeps
// each test self-contained.
const callTool = vi.fn();
const fakeTools = [
  {
    name: "test.lookup",
    description: "test tool lookup",
    inputSchema: z.object({ q: z.string() }),
    handler: async (_ctx: any, input: any) => callTool("test.lookup", input),
  },
  {
    name: "test.transform",
    description: "test tool transform",
    inputSchema: z.object({ q: z.string() }),
    handler: async (_ctx: any, input: any) => callTool("test.transform", input),
  },
];

const ctx = { principal: { userId: "test-user" } };

beforeEach(() => {
  vi.clearAllMocks();
  callTool.mockImplementation(async (name: string, input: any) => ({
    ok: true,
    data: { tool: name, echoed: input },
  }));
  // Reset to default behavior each test — return a fixed id so persistence
  // assertions can refer to "wf-test-1".
  storageMock.createWorkflowInstance.mockImplementation(async (data: any) => ({ id: "wf-test-1", ...data }));
  storageMock.updateWorkflowInstance.mockResolvedValue(undefined);
  storageMock.createWorkflowStep.mockResolvedValue(undefined);
});

function toolUseResponse(opts: { id: string; name: string; input: Record<string, unknown> }) {
  return {
    content: [{ type: "tool_use", id: opts.id, name: opts.name, input: opts.input }],
  };
}

function finalAnswerResponse(text: string) {
  return { content: [{ type: "text", text }] };
}

describe("runAgentLoop", () => {
  it("completes immediately when the model returns a text answer with no tool_use", async () => {
    anthropicMock.messages.create.mockResolvedValueOnce(finalAnswerResponse("Done."));

    const result = await runAgentLoop({ ctx, goal: "say done", opts: { tools: fakeTools } });

    expect(result.endReason).toBe("completed");
    expect(result.finalAnswer).toBe("Done.");
    expect(result.iterations).toBe(1);
    expect(result.steps).toHaveLength(0);
    expect(callTool).not.toHaveBeenCalled();
  });

  it("runs a tool_use turn, feeds the result back, and completes on the next turn", async () => {
    anthropicMock.messages.create
      .mockResolvedValueOnce(
        toolUseResponse({ id: "tu_1", name: "test.lookup", input: { q: "patient 42" } }),
      )
      .mockResolvedValueOnce(finalAnswerResponse("Found patient 42."));

    const result = await runAgentLoop({
      ctx,
      goal: "look up patient 42",
      opts: { tools: fakeTools },
    });

    expect(result.endReason).toBe("completed");
    expect(result.finalAnswer).toBe("Found patient 42.");
    expect(result.iterations).toBe(2);
    expect(result.steps).toHaveLength(1);
    expect(result.steps[0]).toMatchObject({
      iteration: 1,
      toolName: "test.lookup",
      input: { q: "patient 42" },
      result: { ok: true },
    });

    const secondCall = anthropicMock.messages.create.mock.calls[1][0];
    const lastMessage = secondCall.messages.at(-1);
    expect(lastMessage.role).toBe("user");
    expect(lastMessage.content[0].type).toBe("tool_result");
    expect(lastMessage.content[0].is_error).toBe(false);
  });

  it("captures tool failures and feeds them back as is_error: true", async () => {
    callTool.mockResolvedValueOnce({
      ok: false,
      error: { code: "validation.failed", message: "bad input" },
    });
    anthropicMock.messages.create
      .mockResolvedValueOnce(
        toolUseResponse({ id: "tu_1", name: "test.lookup", input: { q: "x" } }),
      )
      .mockResolvedValueOnce(finalAnswerResponse("Could not complete."));

    const result = await runAgentLoop({
      ctx,
      goal: "broken thing",
      opts: { tools: fakeTools },
    });

    expect(result.steps[0].result).toEqual({
      ok: false,
      error: { code: "validation.failed", message: "bad input" },
    });
    const secondCall = anthropicMock.messages.create.mock.calls[1][0];
    expect(secondCall.messages.at(-1).content[0].is_error).toBe(true);
  });

  it("reports 'not_found' when the model invents a tool name", async () => {
    anthropicMock.messages.create
      .mockResolvedValueOnce(
        toolUseResponse({ id: "tu_1", name: "nonexistent.tool", input: { q: "x" } }),
      )
      .mockResolvedValueOnce(finalAnswerResponse("Oops."));

    const result = await runAgentLoop({
      ctx,
      goal: "hallucinate a tool",
      opts: { tools: fakeTools },
    });

    expect(result.steps[0]).toMatchObject({
      toolName: "nonexistent.tool",
      result: { ok: false, error: { code: "not_found" } },
    });
    expect(callTool).not.toHaveBeenCalled();
  });

  it("stops at max_iterations and returns endReason='max_iterations'", async () => {
    anthropicMock.messages.create.mockResolvedValue(
      toolUseResponse({ id: "tu_loop", name: "test.lookup", input: { q: "loop" } }),
    );

    const result = await runAgentLoop({
      ctx,
      goal: "infinite loop",
      opts: { tools: fakeTools, maxIterations: 3 },
    });

    expect(result.endReason).toBe("max_iterations");
    expect(result.iterations).toBe(3);
    expect(result.steps).toHaveLength(3);
  });

  it("returns endReason='error' when the Anthropic call fails", async () => {
    anthropicMock.messages.create.mockRejectedValueOnce(new Error("upstream 502"));
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const result = await runAgentLoop({
      ctx,
      goal: "this will fail",
      opts: { tools: fakeTools },
    });

    expect(result.endReason).toBe("error");
    expect(result.finalAnswer).toMatch(/AI service unavailable/);
    expect(result.steps).toHaveLength(0);
    consoleSpy.mockRestore();
  });

  it("respects the tools option for least-privilege workflows", async () => {
    anthropicMock.messages.create.mockResolvedValueOnce(finalAnswerResponse("Done with subset."));

    await runAgentLoop({
      ctx,
      goal: "use only lookup",
      opts: { tools: [fakeTools[0]] },
    });

    const passedTools = anthropicMock.messages.create.mock.calls[0][0].tools;
    expect(passedTools).toHaveLength(1);
    expect(passedTools[0].name).toBe("test.lookup");
  });

  it("runs multiple tool_use blocks in a single turn sequentially", async () => {
    anthropicMock.messages.create
      .mockResolvedValueOnce({
        content: [
          { type: "tool_use", id: "tu_a", name: "test.lookup", input: { q: "first" } },
          { type: "tool_use", id: "tu_b", name: "test.transform", input: { q: "second" } },
        ],
      })
      .mockResolvedValueOnce(finalAnswerResponse("Both done."));

    const result = await runAgentLoop({
      ctx,
      goal: "parallel tools",
      opts: { tools: fakeTools },
    });

    expect(result.steps).toHaveLength(2);
    expect(result.steps[0].toolName).toBe("test.lookup");
    expect(result.steps[1].toolName).toBe("test.transform");

    const secondCall = anthropicMock.messages.create.mock.calls[1][0];
    const toolResults = secondCall.messages.at(-1).content;
    expect(toolResults).toHaveLength(2);
    expect(toolResults[0].tool_use_id).toBe("tu_a");
    expect(toolResults[1].tool_use_id).toBe("tu_b");
  });
});

describe("runAgentLoop — persistence", () => {
  it("creates a workflow_instance row on start with status='running' and the goal", async () => {
    anthropicMock.messages.create.mockResolvedValueOnce(finalAnswerResponse("Done."));

    await runAgentLoop({ ctx, goal: "persist me", opts: { tools: fakeTools } });

    expect(storageMock.createWorkflowInstance).toHaveBeenCalledOnce();
    const args = storageMock.createWorkflowInstance.mock.calls[0][0];
    expect(args).toMatchObject({
      goal: "persist me",
      status: "running",
      principalUserId: "test-user",
      iterationsUsed: 0,
    });
    // The allowed tool list is recorded for audit.
    expect(args.allowedToolNames).toEqual(["test.lookup", "test.transform"]);
  });

  it("finalizes the workflow_instance row with status='completed' on happy path", async () => {
    anthropicMock.messages.create.mockResolvedValueOnce(finalAnswerResponse("All done."));

    await runAgentLoop({ ctx, goal: "complete me", opts: { tools: fakeTools } });

    expect(storageMock.updateWorkflowInstance).toHaveBeenCalledOnce();
    const [instanceId, patch] = storageMock.updateWorkflowInstance.mock.calls[0];
    expect(instanceId).toBe("wf-test-1");
    expect(patch).toMatchObject({
      status: "completed",
      endReason: "completed",
      finalAnswer: "All done.",
      iterationsUsed: 1,
    });
    expect(patch.completedAt).toBeInstanceOf(Date);
  });

  it("finalizes with status='failed' and error message when Anthropic throws", async () => {
    anthropicMock.messages.create.mockRejectedValueOnce(new Error("upstream 503"));
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    await runAgentLoop({ ctx, goal: "this will fail", opts: { tools: fakeTools } });

    const patch = storageMock.updateWorkflowInstance.mock.calls[0][1];
    expect(patch).toMatchObject({
      status: "failed",
      endReason: "error",
      errorMessage: "upstream 503",
    });
    consoleSpy.mockRestore();
  });

  it("finalizes with status='max_iterations' when the cap is hit", async () => {
    anthropicMock.messages.create.mockResolvedValue(
      toolUseResponse({ id: "tu_loop", name: "test.lookup", input: { q: "loop" } }),
    );

    await runAgentLoop({ ctx, goal: "infinite", opts: { tools: fakeTools, maxIterations: 2 } });

    const patch = storageMock.updateWorkflowInstance.mock.calls[0][1];
    expect(patch.status).toBe("max_iterations");
    expect(patch.iterationsUsed).toBe(2);
  });

  it("persists a workflow_step row for every tool invocation", async () => {
    anthropicMock.messages.create
      .mockResolvedValueOnce(
        toolUseResponse({ id: "tu_1", name: "test.lookup", input: { q: "a" } }),
      )
      .mockResolvedValueOnce(
        toolUseResponse({ id: "tu_2", name: "test.transform", input: { q: "b" } }),
      )
      .mockResolvedValueOnce(finalAnswerResponse("Done."));

    await runAgentLoop({ ctx, goal: "two-step", opts: { tools: fakeTools } });

    expect(storageMock.createWorkflowStep).toHaveBeenCalledTimes(2);
    const stepCalls = storageMock.createWorkflowStep.mock.calls.map((c) => c[0]);
    expect(stepCalls[0]).toMatchObject({
      instanceId: "wf-test-1",
      iteration: 1,
      toolName: "test.lookup",
      input: { q: "a" },
    });
    expect(stepCalls[0].result).toMatchObject({ ok: true });
    expect(stepCalls[0].durationMs).toBeGreaterThanOrEqual(0);

    expect(stepCalls[1]).toMatchObject({
      iteration: 2,
      toolName: "test.transform",
      input: { q: "b" },
    });
  });

  it("persists a step even when the model invents a tool name", async () => {
    anthropicMock.messages.create
      .mockResolvedValueOnce(
        toolUseResponse({ id: "tu_1", name: "no.such.tool", input: { q: "x" } }),
      )
      .mockResolvedValueOnce(finalAnswerResponse("Oops."));

    await runAgentLoop({ ctx, goal: "hallucinate", opts: { tools: fakeTools } });

    expect(storageMock.createWorkflowStep).toHaveBeenCalledOnce();
    const step = storageMock.createWorkflowStep.mock.calls[0][0];
    expect(step.toolName).toBe("no.such.tool");
    expect(step.result).toMatchObject({ ok: false, error: { code: "not_found" } });
  });

  it("continues the loop in-memory if the DB create fails", async () => {
    storageMock.createWorkflowInstance.mockRejectedValueOnce(new Error("db down"));
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    anthropicMock.messages.create.mockResolvedValueOnce(finalAnswerResponse("Survived."));

    const result = await runAgentLoop({ ctx, goal: "db is dead", opts: { tools: fakeTools } });

    // The agent loop still returned a clean result.
    expect(result.endReason).toBe("completed");
    expect(result.finalAnswer).toBe("Survived.");
    // No step or update attempted because there's no instance id.
    expect(storageMock.createWorkflowStep).not.toHaveBeenCalled();
    expect(storageMock.updateWorkflowInstance).not.toHaveBeenCalled();
    consoleSpy.mockRestore();
  });
});

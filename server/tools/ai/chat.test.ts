import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../../services/ai", () => ({ askClaude: vi.fn(), anthropic: {} as any }));

import { askClaude } from "../../services/ai";
import { runTool } from "../runner";
import { chatTool } from "./chat";
import { ToolErrorCode } from "../types";

const askClaudeMock = vi.mocked(askClaude);
const ctx = { principal: { userId: "test-user" } };

beforeEach(() => vi.clearAllMocks());

describe("ai.chat tool", () => {
  it("returns the AI response on a valid call", async () => {
    askClaudeMock.mockResolvedValue("Here are some thoughts on your treatment plan.");
    const result = await runTool(chatTool, ctx, { content: "Help me plan an All-on-4" });
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.response).toMatch(/treatment plan/);
  });

  it("falls back to a polite message when the AI returns empty", async () => {
    askClaudeMock.mockResolvedValue("");
    const result = await runTool(chatTool, ctx, { content: "anything" });
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.response).toMatch(/couldn't generate/i);
  });

  it("rejects empty content with validation failure (no AI call)", async () => {
    const result = await runTool(chatTool, ctx, { content: "" });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.code).toBe(ToolErrorCode.ValidationFailed);
    expect(askClaudeMock).not.toHaveBeenCalled();
  });
});

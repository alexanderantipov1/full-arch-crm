import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../../services/ai", () => ({ askClaude: vi.fn(), anthropic: {} as any }));

import { askClaude } from "../../services/ai";
import { runTool } from "../runner";
import { suggestReplyTool } from "./suggestReply";
import { ToolErrorCode } from "../types";

const askClaudeMock = vi.mocked(askClaude);
const ctx = { principal: { userId: "test-user" } };

beforeEach(() => vi.clearAllMocks());

describe("messaging.suggestReply tool", () => {
  it("encodes the SMS channel as a brief-message hint to the AI", async () => {
    askClaudeMock.mockResolvedValue("Got it, see you tomorrow at 10!");
    await runTool(suggestReplyTool, ctx, {
      patientName: "Jane",
      lastMessage: "What time is my appointment?",
      channel: "sms",
    });
    const userMessage = askClaudeMock.mock.calls[0][1];
    expect(userMessage).toMatch(/SMS/i);
    expect(userMessage).toContain("160 characters");
  });

  it("encodes the email channel as a professional-email hint", async () => {
    askClaudeMock.mockResolvedValue("ok");
    await runTool(suggestReplyTool, ctx, {
      patientName: "Jane",
      lastMessage: "Question",
      channel: "email",
    });
    expect(askClaudeMock.mock.calls[0][1]).toMatch(/professional email/);
  });

  it("rejects empty last message", async () => {
    const result = await runTool(suggestReplyTool, ctx, { lastMessage: "" });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.code).toBe(ToolErrorCode.ValidationFailed);
  });
});

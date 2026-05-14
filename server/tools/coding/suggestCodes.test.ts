import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the AI service so the test never touches Anthropic.
vi.mock("../../services/ai", () => ({
  askClaude: vi.fn(),
  anthropic: {} as any,
}));

import { askClaude } from "../../services/ai";
import { runTool } from "../runner";
import { suggestCodesTool } from "./suggestCodes";
import { ToolErrorCode } from "../types";

const askClaudeMock = vi.mocked(askClaude);

const ctx = {
  principal: { userId: "test-user", email: "test@example.com" },
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("coding.suggestCodes tool", () => {
  it("returns the parsed AI suggestion on a valid call", async () => {
    askClaudeMock.mockResolvedValue(
      JSON.stringify({
        suggestedCDT: [{ code: "D6010", description: "Implant", fee: 2200 }],
        suggestedICD10: [{ code: "K08.1", description: "Edentulism", priority: 1 }],
        confidenceScore: 92,
      }),
    );

    const result = await runTool(suggestCodesTool, ctx, {
      diagnosis: "complete edentulism",
      procedures: "full-arch upper implant",
      clinicalNotes: "patient reports difficulty chewing",
    });

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.suggestedCDT?.[0].code).toBe("D6010");
      expect(result.data.confidenceScore).toBe(92);
    }
    // Verify the tool fed the user message into the prompt, not just the system prompt.
    expect(askClaudeMock).toHaveBeenCalledOnce();
    const userMessage = askClaudeMock.mock.calls[0][1];
    expect(userMessage).toContain("complete edentulism");
    expect(userMessage).toContain("full-arch upper implant");
    expect(userMessage).toContain("patient reports difficulty chewing");
  });

  it("treats missing clinicalNotes as 'Not provided' rather than rejecting", async () => {
    askClaudeMock.mockResolvedValue("{}");

    const result = await runTool(suggestCodesTool, ctx, {
      diagnosis: "edentulism",
      procedures: "implant",
    });

    expect(result.ok).toBe(true);
    const userMessage = askClaudeMock.mock.calls[0][1];
    expect(userMessage).toContain("Not provided");
  });

  it("rejects empty diagnosis with a validation error (no AI call)", async () => {
    const result = await runTool(suggestCodesTool, ctx, {
      diagnosis: "   ",
      procedures: "implant",
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe(ToolErrorCode.ValidationFailed);
      expect(result.error.message).toMatch(/diagnosis/i);
    }
    expect(askClaudeMock).not.toHaveBeenCalled();
  });

  it("rejects empty procedures with a validation error (no AI call)", async () => {
    const result = await runTool(suggestCodesTool, ctx, {
      diagnosis: "edentulism",
      procedures: "",
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe(ToolErrorCode.ValidationFailed);
    }
    expect(askClaudeMock).not.toHaveBeenCalled();
  });

  it("returns ai.invalid_response when the AI returns non-JSON text", async () => {
    askClaudeMock.mockResolvedValue("not even close to JSON");

    const result = await runTool(suggestCodesTool, ctx, {
      diagnosis: "edentulism",
      procedures: "implant",
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe(ToolErrorCode.AiResponseInvalid);
    }
  });

  it("returns ai.call_failed when the AI service throws", async () => {
    askClaudeMock.mockRejectedValue(new Error("upstream 503"));

    const result = await runTool(suggestCodesTool, ctx, {
      diagnosis: "edentulism",
      procedures: "implant",
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe(ToolErrorCode.AiCallFailed);
      // In non-prod the upstream error message is allowed in details for debugging.
      expect(result.error.message).not.toMatch(/upstream 503/);
    }
  });
});

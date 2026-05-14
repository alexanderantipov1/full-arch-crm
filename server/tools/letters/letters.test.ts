import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../../services/ai", () => ({ askClaude: vi.fn(), anthropic: {} as any }));

import { askClaude } from "../../services/ai";
import { runTool } from "../runner";
import { medicalNecessityLetterTool } from "./medicalNecessity";
import { appealLetterTool } from "./appeal";
import { ToolErrorCode } from "../types";

const askClaudeMock = vi.mocked(askClaude);
const ctx = { principal: { userId: "test-user" } };

beforeEach(() => vi.clearAllMocks());

describe("letters.medicalNecessity tool", () => {
  it("returns the generated letter when the AI responds", async () => {
    askClaudeMock.mockResolvedValue("Dear Sir/Madam, the patient requires...");
    const result = await runTool(medicalNecessityLetterTool, ctx, {
      patientName: "Jane Doe",
      diagnosis: "K08.1 complete edentulism",
      procedures: "D6010, D6114",
    });
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.letter).toMatch(/Dear/);
  });

  it("rejects missing patient name with validation failure", async () => {
    const result = await runTool(medicalNecessityLetterTool, ctx, { patientName: "" });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.code).toBe(ToolErrorCode.ValidationFailed);
  });
});

describe("letters.appeal tool", () => {
  it("includes the denial reason and claim number in the AI prompt", async () => {
    askClaudeMock.mockResolvedValue("Generated appeal letter.");
    await runTool(appealLetterTool, ctx, {
      patientName: "John Smith",
      claimNumber: "CLM-12345",
      denialReason: "Not medically necessary",
    });
    const userMessage = askClaudeMock.mock.calls[0][1];
    expect(userMessage).toContain("CLM-12345");
    expect(userMessage).toContain("Not medically necessary");
  });
});

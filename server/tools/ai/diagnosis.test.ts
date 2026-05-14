import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../../services/ai", () => ({ askClaude: vi.fn(), anthropic: {} as any }));

import { askClaude } from "../../services/ai";
import { runTool } from "../runner";
import { diagnosisTool } from "./diagnosis";

const askClaudeMock = vi.mocked(askClaude);
const ctx = { principal: { userId: "test-user" } };

beforeEach(() => vi.clearAllMocks());

describe("ai.diagnosis tool", () => {
  it("forwards patient info, complaint, and conditions into the prompt", async () => {
    askClaudeMock.mockResolvedValue("Diagnosis: K08.1...");
    const result = await runTool(diagnosisTool, ctx, {
      patientInfo: { age: 67 },
      chiefComplaint: "can't chew solid food",
      dentalConditions: { edentulism: true },
    });
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.diagnosis).toContain("K08.1");

    const userMessage = askClaudeMock.mock.calls[0][1];
    expect(userMessage).toContain("can't chew");
    expect(userMessage).toContain("edentulism");
    expect(userMessage).toContain("67");
  });

  it("handles missing optional fields gracefully", async () => {
    askClaudeMock.mockResolvedValue("Generic diagnosis");
    const result = await runTool(diagnosisTool, ctx, {});
    expect(result.ok).toBe(true);
  });
});

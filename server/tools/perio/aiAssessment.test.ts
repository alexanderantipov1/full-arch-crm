import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../../services/ai", () => ({ askClaude: vi.fn(), anthropic: {} as any }));

import { askClaude } from "../../services/ai";
import { runTool } from "../runner";
import { perioAssessmentTool } from "./aiAssessment";

const askClaudeMock = vi.mocked(askClaude);
const ctx = { principal: { userId: "test-user" } };

beforeEach(() => vi.clearAllMocks());

describe("perio.aiAssessment tool", () => {
  it("computes probing stats correctly and feeds them into the AI prompt", async () => {
    askClaudeMock.mockResolvedValue("Stage II periodontitis, recommend D4341.");
    const result = await runTool(perioAssessmentTool, ctx, {
      patientName: "Jane Doe",
      probingData: {
        "1": { facialProbing: [2, 3, 4], lingualProbing: [3, 4, 5], facialBop: [false, true, true], lingualBop: [false, false, true] },
        "2": { missing: true },
        "3": { facialProbing: [6, 7, 8], lingualProbing: [5, 6, 7], facialBop: [true, true, true], lingualBop: [true, true, false] },
      },
    });

    expect(result.ok).toBe(true);
    if (!result.ok) return;

    // tooth 1: 6 sites, 3 ≥4, 0 ≥6. tooth 3: 6 sites, all ≥4, 5 ≥6. tooth 2 skipped (missing).
    expect(result.data.stats.totalSites).toBe(12);
    expect(result.data.stats.sitesGt4).toBe(9);
    expect(result.data.stats.sitesGt6).toBe(5);
    expect(result.data.stats.bopPct).toBeGreaterThan(0);

    // Stats made it into the user prompt for the AI.
    const userMessage = askClaudeMock.mock.calls[0][1];
    expect(userMessage).toContain("Sites ≥4mm: 9");
    expect(userMessage).toContain("Sites ≥6mm: 5");
  });

  it("returns zero stats when all teeth are missing", async () => {
    askClaudeMock.mockResolvedValue("No probing data — patient is edentulous.");
    const result = await runTool(perioAssessmentTool, ctx, {
      probingData: { "1": { missing: true }, "2": { missing: true } },
    });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.stats.totalSites).toBe(0);
      expect(result.data.stats.avgDepth).toBe("0");
    }
  });
});

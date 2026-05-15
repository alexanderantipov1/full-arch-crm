import { describe, it, expect, vi, beforeEach } from "vitest";

const askClaudeMock = vi.hoisted(() => vi.fn());

vi.mock("../../services/ai", () => ({
  askClaude: askClaudeMock,
  anthropic: {} as any,
}));

import { runTool } from "../runner";
import { specialtyRecommendationsTool } from "./specialtyRecommendations";

const ctx = { principal: { userId: "test-user" } };

beforeEach(() => vi.clearAllMocks());

describe("onboarding.specialtyRecommendations tool", () => {
  it("parses a valid AI JSON response", async () => {
    askClaudeMock.mockResolvedValue(JSON.stringify({
      welcome: "Welcome, periodontist!",
      modules: [{ title: "Perio Charting", url: "/perio", reason: "Daily charting workflow" }],
    }));

    const result = await runTool(specialtyRecommendationsTool, ctx, { specialty: "periodontist" });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.welcome).toMatch(/periodontist/i);
      expect(result.data.modules).toHaveLength(1);
    }
  });

  it("falls back to a generic welcome when the AI returns non-JSON (no error surfaced)", async () => {
    askClaudeMock.mockResolvedValue("no json here at all");
    const result = await runTool(specialtyRecommendationsTool, ctx, { specialty: "orthodontist" });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.welcome).toMatch(/orthodontist/);
      expect(result.data.modules).toEqual([]);
    }
  });

  it("falls back to a generic welcome when the AI throws (onboarding never errors)", async () => {
    askClaudeMock.mockRejectedValue(new Error("AI down"));
    // Spy and silence the error log so this test doesn't pollute output.
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const result = await runTool(specialtyRecommendationsTool, ctx, { specialty: "endodontist" });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.modules).toEqual([]);
      expect(result.data.welcome).toMatch(/Welcome/);
    }
    consoleSpy.mockRestore();
  });
});

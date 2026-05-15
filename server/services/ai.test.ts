import { afterEach, describe, expect, it } from "vitest";
import { AiPolicyBlockedError, askClaude, hasSignedAnthropicBaa } from "./ai";

const originalBaa = process.env.ANTHROPIC_BAA_SIGNED;

afterEach(() => {
  if (originalBaa === undefined) {
    delete process.env.ANTHROPIC_BAA_SIGNED;
  } else {
    process.env.ANTHROPIC_BAA_SIGNED = originalBaa;
  }
});

describe("AI vendor policy", () => {
  it("treats Anthropic as not BAA-covered unless explicitly configured", () => {
    delete process.env.ANTHROPIC_BAA_SIGNED;
    expect(hasSignedAnthropicBaa()).toBe(false);

    process.env.ANTHROPIC_BAA_SIGNED = "true";
    expect(hasSignedAnthropicBaa()).toBe(true);
  });

  it("blocks PHI-bound Claude calls when no Anthropic BAA is configured", async () => {
    delete process.env.ANTHROPIC_BAA_SIGNED;

    await expect(
      askClaude("system", "Patient: Jane Doe", 100, {
        dataClass: "phi",
        purpose: "unit_test_phi",
      }),
    ).rejects.toBeInstanceOf(AiPolicyBlockedError);
  });
});

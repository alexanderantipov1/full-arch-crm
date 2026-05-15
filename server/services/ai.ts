import Anthropic from "@anthropic-ai/sdk";

export const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

export type AiDataClass = "deidentified" | "ops_safe" | "phi";

export class AiPolicyBlockedError extends Error {
  readonly code = "ai.policy_blocked" as const;

  constructor(
    message: string,
    readonly dataClass: AiDataClass,
    readonly purpose?: string,
  ) {
    super(message);
    this.name = "AiPolicyBlockedError";
  }
}

export function hasSignedAnthropicBaa(): boolean {
  return process.env.ANTHROPIC_BAA_SIGNED === "true";
}

export interface AskClaudeOptions {
  dataClass: AiDataClass;
  purpose?: string;
}

// Single-turn Claude call. Use when the prompt fully describes the task and
// you don't need conversation state. Returns the text block content or "" if
// the model returned something non-textual (image, tool use, etc.).
export async function askClaude(
  systemPrompt: string,
  userMessage: string,
  maxTokens = 1500,
  options: AskClaudeOptions = { dataClass: "phi" },
): Promise<string> {
  if (options.dataClass === "phi" && !hasSignedAnthropicBaa()) {
    throw new AiPolicyBlockedError(
      "Anthropic BAA is not configured; PHI may not be sent to Anthropic.",
      options.dataClass,
      options.purpose,
    );
  }

  const response = await anthropic.messages.create({
    model: "claude-opus-4-5",
    max_tokens: maxTokens,
    system: systemPrompt,
    messages: [{ role: "user", content: userMessage }],
  });
  const block = response.content[0];
  return block.type === "text" ? block.text : "";
}

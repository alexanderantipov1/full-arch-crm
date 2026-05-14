import Anthropic from "@anthropic-ai/sdk";

export const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

// Single-turn Claude call. Use when the prompt fully describes the task and
// you don't need conversation state. Returns the text block content or "" if
// the model returned something non-textual (image, tool use, etc.).
export async function askClaude(
  systemPrompt: string,
  userMessage: string,
  maxTokens = 1500,
): Promise<string> {
  const response = await anthropic.messages.create({
    model: "claude-opus-4-5",
    max_tokens: maxTokens,
    system: systemPrompt,
    messages: [{ role: "user", content: userMessage }],
  });
  const block = response.content[0];
  return block.type === "text" ? block.text : "";
}

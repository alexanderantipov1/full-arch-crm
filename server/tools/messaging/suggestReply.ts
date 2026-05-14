import { z } from "zod";
import { askClaude } from "../../services/ai";
import { defineTool, ToolErrorCode } from "../types";

const inputSchema = z.object({
  patientName: z.string().optional(),
  lastMessage: z.string().trim().min(1, "Last message is required"),
  channel: z.enum(["sms", "email", "in_app"]).optional(),
});

export type SuggestReplyInput = z.infer<typeof inputSchema>;
export interface SuggestReplyOutput {
  suggestion: string;
}

export const suggestReplyTool = defineTool<SuggestReplyInput, SuggestReplyOutput>({
  name: "messaging.suggestReply",
  description: "Draft a HIPAA-compliant reply to a patient message, channel-aware (sms/email/in-app).",
  inputSchema,
  async handler(_ctx, input) {
    const channelCtx =
      input.channel === "sms"
        ? "a brief SMS (under 160 characters if possible)"
        : input.channel === "email"
          ? "a professional email"
          : "an in-app message";

    try {
      const suggestion = await askClaude(
        `You are a helpful dental practice assistant. Write professional, empathetic, HIPAA-compliant replies. Do not include placeholders or brackets. Return only the ready-to-send message text with no additional commentary.`,
        `Draft ${channelCtx} reply for patient ${input.patientName || "the patient"}.\n\nPatient's last message: "${input.lastMessage}"`,
      );
      return { ok: true, data: { suggestion } };
    } catch {
      return {
        ok: false,
        error: { code: ToolErrorCode.AiCallFailed, message: "AI suggestion failed" },
      };
    }
  },
});

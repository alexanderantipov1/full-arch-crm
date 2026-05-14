import { z } from "zod";
import { askClaude } from "../../services/ai";
import { defineTool, ToolErrorCode } from "../types";

const inputSchema = z.object({
  patientName: z.string().trim().min(1, "Patient name is required"),
  claimNumber: z.string().optional(),
  denialReason: z.string().optional(),
  originalDiagnosis: z.string().optional(),
  procedures: z.string().optional(),
});

export type AppealLetterInput = z.infer<typeof inputSchema>;
export interface AppealLetterOutput {
  letter: string;
}

export const appealLetterTool = defineTool<AppealLetterInput, AppealLetterOutput>({
  name: "letters.appeal",
  description: "Draft an insurance appeal letter addressing a specific denial reason with clinical evidence.",
  inputSchema,
  async handler(_ctx, input) {
    const userMessage = `Generate a professional insurance appeal letter for a denied dental implant claim:

Patient: ${input.patientName}
Claim Number: ${input.claimNumber ?? ""}
Denial Reason: ${input.denialReason ?? ""}
Original Diagnosis: ${input.originalDiagnosis ?? ""}
Procedures: ${input.procedures ?? ""}

The appeal should:
1. Professionally address the specific denial reason
2. Cite relevant clinical evidence and guidelines
3. Reference peer-reviewed literature if applicable
4. Include strong medical necessity arguments
5. Request reconsideration with specific action items`;

    try {
      const letter = await askClaude(
        "You are an expert at writing insurance appeal letters for dental procedures. Create persuasive, evidence-based appeals.",
        userMessage,
        2000,
      );
      return { ok: true, data: { letter } };
    } catch {
      return {
        ok: false,
        error: { code: ToolErrorCode.AiCallFailed, message: "AI service unavailable" },
      };
    }
  },
});

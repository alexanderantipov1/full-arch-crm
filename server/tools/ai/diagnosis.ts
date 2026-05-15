import { z } from "zod";
import { askClaude } from "../../services/ai";
import { defineTool, ToolErrorCode } from "../types";

const inputSchema = z.object({
  patientInfo: z.unknown().optional(),
  chiefComplaint: z.string().optional(),
  dentalConditions: z.unknown().optional(),
});

export type DiagnosisInput = z.infer<typeof inputSchema>;
export interface DiagnosisOutput {
  diagnosis: string;
}

export const diagnosisTool = defineTool<DiagnosisInput, DiagnosisOutput>({
  name: "ai.diagnosis",
  description: "Generate a diagnosis + treatment plan for full arch dental implants from patient info, chief complaint, and dental conditions.",
  inputSchema,
  async handler(_ctx, input) {
    const userMessage = `Based on the following patient information, provide a diagnosis and treatment recommendations for full arch dental implants:

Patient Info: ${JSON.stringify(input.patientInfo ?? {})}
Chief Complaint: ${input.chiefComplaint ?? ""}
Dental Conditions: ${JSON.stringify(input.dentalConditions ?? {})}

Please provide:
1. Primary diagnosis with ICD-10 code
2. Treatment recommendations (All-on-4, All-on-6, or alternative)
3. Estimated procedure list with CDT codes
4. Key considerations for treatment planning
5. Suggested pre-operative requirements`;

    try {
      const diagnosis = await askClaude(
        "You are an expert dental implant treatment planning assistant. Provide detailed, clinically accurate recommendations.",
        userMessage,
        2000,
        { dataClass: "phi", purpose: "ai_diagnosis_assistance" },
      );
      return { ok: true, data: { diagnosis } };
    } catch {
      return {
        ok: false,
        error: { code: ToolErrorCode.AiCallFailed, message: "AI service unavailable" },
      };
    }
  },
});

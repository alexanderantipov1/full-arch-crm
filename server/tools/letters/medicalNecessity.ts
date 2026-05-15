import { z } from "zod";
import { askClaude } from "../../services/ai";
import { defineTool, ToolErrorCode } from "../types";

const inputSchema = z.object({
  patientName: z.string().trim().min(1, "Patient name is required"),
  dateOfBirth: z.string().optional(),
  diagnosis: z.string().optional(),
  procedures: z.string().optional(),
  justification: z.string().optional(),
});

export type MedicalNecessityInput = z.infer<typeof inputSchema>;
export interface MedicalNecessityOutput {
  letter: string;
}

export const medicalNecessityLetterTool = defineTool<MedicalNecessityInput, MedicalNecessityOutput>({
  name: "letters.medicalNecessity",
  description: "Draft a medical necessity letter for dental implant insurance submission.",
  inputSchema,
  async handler(_ctx, input) {
    const userMessage = `Generate a professional medical necessity letter for dental implant treatment:

Patient: ${input.patientName}
DOB: ${input.dateOfBirth ?? ""}
Diagnosis: ${input.diagnosis ?? ""}
Procedures: ${input.procedures ?? ""}
Additional Justification: ${input.justification ?? ""}

The letter should:
1. Be professionally formatted
2. Include relevant ICD-10 and CDT codes
3. Emphasize functional impairment and quality of life impact
4. Reference clinical evidence for implant therapy
5. Be suitable for insurance submission`;

    try {
      const letter = await askClaude(
        "You are an expert at writing medical necessity letters for dental implant procedures. Create compelling, evidence-based letters.",
        userMessage,
        2000,
        { dataClass: "phi", purpose: "medical_necessity_letter" },
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

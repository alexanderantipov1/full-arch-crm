import { z } from "zod";
import { askClaude } from "../../services/ai";
import { defineTool, ToolErrorCode } from "../types";

// First tool migrated to the new layer. Originally lived inline in
// server/routes.ts as the /api/coding/suggest handler. The behavior is
// unchanged; what changed is that the AI prompt, validation, and JSON
// parsing all live in one place that's testable and importable.

const inputSchema = z.object({
  diagnosis: z.string().trim().min(1, "Diagnosis is required"),
  procedures: z.string().trim().min(1, "Procedures is required"),
  clinicalNotes: z.string().optional(),
});

export type SuggestCodesInput = z.infer<typeof inputSchema>;

// The AI returns this shape (we don't validate it strictly — the dental
// billing UI tolerates partial responses — but the type documents intent).
export interface SuggestCodesOutput {
  suggestedCDT?: Array<{ code: string; description: string; fee?: number }>;
  suggestedCPT?: Array<{ code: string; description: string; medicalCrossCode?: boolean }>;
  suggestedICD10?: Array<{ code: string; description: string; priority?: number }>;
  medicalNecessityNotes?: string;
  confidenceScore?: number;
  warnings?: string[];
}

const SYSTEM_PROMPT = `You are an expert dental billing coder specializing in full arch dental implants. Your role is to suggest the most appropriate CDT codes, CPT codes (for medical insurance cross-coding), and ICD-10 diagnosis codes that maximize insurance approval rates while maintaining compliance.

For full arch dental implants, focus on:
- Medical necessity documentation (functional impairment, nutritional concerns, airway issues)
- Appropriate modifier usage (RT/LT for laterality, 22 for complexity)
- Supporting diagnoses that strengthen medical necessity

Common CDT codes for full arch:
- D6010: Surgical placement of implant body
- D6056: Prefabricated abutment
- D6114: Implant/abutment supported fixed denture for completely edentulous arch
- D7210: Extraction with flap elevation
- D7953: Bone replacement graft

Common ICD-10 codes for medical necessity:
- K08.1: Complete loss of teeth (edentulism)
- K08.109: Complete loss of teeth, unspecified cause
- K08.419: Partial loss of teeth, unspecified cause
- R63.3: Feeding difficulties and mismanagement (nutritional impact)
- G47.33: Obstructive sleep apnea (if applicable)
- E11.x: Type 2 diabetes mellitus (if applicable for bone healing)

Return your response as valid JSON only (no markdown, no code blocks) with this structure:
{"suggestedCDT": [{"code": "D6010", "description": "...", "fee": 2200}], "suggestedCPT": [{"code": "21248", "description": "...", "medicalCrossCode": true}], "suggestedICD10": [{"code": "K08.1", "description": "...", "priority": 1}], "medicalNecessityNotes": "...", "confidenceScore": 95, "warnings": []}`;

export const suggestCodesTool = defineTool<SuggestCodesInput, SuggestCodesOutput>({
  name: "coding.suggestCodes",
  description:
    "Suggest CDT, CPT (medical cross-coding), and ICD-10 codes for a dental implant procedure based on diagnosis, procedures, and clinical notes.",
  inputSchema,

  async handler(_ctx, input) {
    const userMessage = `Suggest appropriate billing codes for:
Diagnosis: ${input.diagnosis}
Procedures: ${input.procedures}
Clinical Notes: ${input.clinicalNotes ?? "Not provided"}`;

    let raw: string;
    try {
      raw = await askClaude(SYSTEM_PROMPT, userMessage, 1500);
    } catch (err: any) {
      return {
        ok: false,
        error: {
          code: ToolErrorCode.AiCallFailed,
          message: "AI service unavailable",
          details: process.env.NODE_ENV === "production" ? undefined : { reason: err?.message },
        },
      };
    }

    try {
      const data = JSON.parse(raw || "{}") as SuggestCodesOutput;
      return { ok: true, data };
    } catch {
      return {
        ok: false,
        error: {
          code: ToolErrorCode.AiResponseInvalid,
          message: "AI returned non-JSON response",
        },
      };
    }
  },
});

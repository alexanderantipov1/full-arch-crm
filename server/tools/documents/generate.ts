import { z } from "zod";
import { askClaude } from "../../services/ai";
import { phiService, PhiAccessDeniedError } from "../../services/phi";
import { defineTool, ToolErrorCode } from "../types";

// PHI-touching tool. Reads patient + medical history + treatment plans via
// PhiService, which checks the principal's `phi.read` capability and writes
// an audit row for every access — allowed or denied. Persisting the doc
// also goes through PhiService.createGeneratedDocument (`phi.write` check).
//
// The tool itself never touches `storage` directly. That's the rule: PHI
// data only flows through PhiService.

const documentType = z.enum([
  "medical-necessity",
  "operative-report",
  "progress-note",
  "history-physical",
  "peer-to-peer",
]);

const inputSchema = z.object({
  patientId: z.number().int().positive(),
  documentType,
  additionalContext: z.string().optional(),
});

export type GenerateDocumentInput = z.infer<typeof inputSchema>;
export interface GenerateDocumentOutput {
  content: string;
  documentId: number;
}

const documentTemplates: Record<string, string> = {
  "medical-necessity":
    "Generate a comprehensive medical necessity letter for insurance submission. Include clinical justification for full arch dental implants, functional impairment documentation, and reference to ADA guidelines.",
  "operative-report":
    "Generate a detailed operative report for dental implant surgery. Include procedure details, implant specifications, bone quality, complications if any, and post-operative instructions.",
  "progress-note":
    "Generate a clinical progress note documenting the patient's treatment progress, healing status, and any clinical observations.",
  "history-physical":
    "Generate a comprehensive History and Physical (H&P) document from the patient's intake data, including chief complaint, medical history, review of systems, and physical examination findings.",
  "peer-to-peer":
    "Generate talking points and clinical justification for a peer-to-peer review with an insurance medical director. Focus on medical necessity and clinical evidence.",
};

function titleCase(s: string): string {
  return s.replace(/-/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
}

export const generateDocumentTool = defineTool<GenerateDocumentInput, GenerateDocumentOutput>({
  name: "documents.generate",
  description: "Generate a clinical document (medical necessity, operative report, etc.) using patient PHI as context, and persist the result.",
  inputSchema,
  async handler(ctx, input) {
    let patient;
    let medicalHistory;
    let treatmentPlans;

    try {
      patient = await phiService.getPatient(ctx.principal, input.patientId);
      if (!patient) {
        return {
          ok: false,
          error: { code: ToolErrorCode.NotFound, message: "Patient not found" },
        };
      }
      medicalHistory = await phiService.getMedicalHistory(ctx.principal, input.patientId);
      treatmentPlans = await phiService.getTreatmentPlansByPatient(ctx.principal, input.patientId);
    } catch (err) {
      if (err instanceof PhiAccessDeniedError) {
        return {
          ok: false,
          error: { code: ToolErrorCode.PhiAccessDenied, message: err.message },
        };
      }
      throw err;
    }

    const userMessage = `${documentTemplates[input.documentType]}

Patient Information:
- Name: ${patient.firstName} ${patient.lastName}
- DOB: ${patient.dateOfBirth}
- Medical History: ${JSON.stringify(medicalHistory ?? {})}
- Treatment Plans: ${JSON.stringify(treatmentPlans ?? [])}
${input.additionalContext ? `\nAdditional Context: ${input.additionalContext}` : ""}

Please generate professional, HIPAA-compliant clinical documentation.`;

    let content: string;
    try {
      content = await askClaude(
        "You are an expert dental billing specialist generating clinical documentation for full arch dental implant procedures. Generate professional, compliant documentation that supports medical necessity and insurance claims.",
        userMessage,
        2000,
      );
    } catch {
      return {
        ok: false,
        error: { code: ToolErrorCode.AiCallFailed, message: "AI service unavailable" },
      };
    }

    try {
      const savedDoc = await phiService.createGeneratedDocument(ctx.principal, {
        patientId: input.patientId,
        documentType: input.documentType,
        title: `${titleCase(input.documentType)} - ${patient.firstName} ${patient.lastName}`,
        content,
        metadata: { additionalContext: input.additionalContext },
      });
      return { ok: true, data: { content, documentId: savedDoc.id } };
    } catch (err) {
      if (err instanceof PhiAccessDeniedError) {
        return {
          ok: false,
          error: { code: ToolErrorCode.PhiAccessDenied, message: err.message },
        };
      }
      throw err;
    }
  },
});

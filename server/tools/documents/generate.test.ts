import { describe, it, expect, vi, beforeEach } from "vitest";

const storageMock = vi.hoisted(() => ({
  getPatient: vi.fn(),
  getMedicalHistory: vi.fn(),
  getTreatmentPlansByPatient: vi.fn(),
  createGeneratedDocument: vi.fn(),
  // Audit log mock — PhiService writes here. We don't assert on its calls in
  // every test; just make sure the writes don't throw.
  createAuditLog: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("../../services/ai", () => ({ askClaude: vi.fn(), anthropic: {} as any }));
vi.mock("../../storage", () => ({ storage: storageMock }));

import { askClaude } from "../../services/ai";
import { runTool } from "../runner";
import { generateDocumentTool } from "./generate";
import { ToolErrorCode, makePrincipal } from "../types";

const askClaudeMock = vi.mocked(askClaude);

// The tool is PHI-touching, so the principal must have phi.read + phi.write.
const phiPrincipal = makePrincipal({
  userId: "test-user",
  email: "test@example.com",
  capabilities: ["phi.read", "phi.write"],
});
const ctx = { principal: phiPrincipal };

beforeEach(() => {
  vi.clearAllMocks();
  storageMock.createAuditLog.mockResolvedValue(undefined);
});

describe("documents.generate tool (PHI-touching, gated by PhiService)", () => {
  it("returns not_found when the patient doesn't exist (no AI call, no doc written)", async () => {
    storageMock.getPatient.mockResolvedValue(undefined);

    const result = await runTool(generateDocumentTool, ctx, {
      patientId: 9999,
      documentType: "medical-necessity",
    });

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.code).toBe(ToolErrorCode.NotFound);
    expect(askClaudeMock).not.toHaveBeenCalled();
    expect(storageMock.createGeneratedDocument).not.toHaveBeenCalled();
  });

  it("rejects invalid documentType with validation failure", async () => {
    const result = await runTool(generateDocumentTool, ctx, {
      patientId: 1,
      documentType: "not-a-real-type",
    });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.code).toBe(ToolErrorCode.ValidationFailed);
    expect(storageMock.getPatient).not.toHaveBeenCalled();
  });

  it("generates + persists a document on the happy path", async () => {
    storageMock.getPatient.mockResolvedValue({
      id: 1,
      firstName: "Jane",
      lastName: "Doe",
      dateOfBirth: "1960-01-01",
    });
    storageMock.getMedicalHistory.mockResolvedValue({ conditions: ["diabetes"] });
    storageMock.getTreatmentPlansByPatient.mockResolvedValue([]);
    askClaudeMock.mockResolvedValue("Dear insurance carrier...");
    storageMock.createGeneratedDocument.mockResolvedValue({ id: 77 });

    const result = await runTool(generateDocumentTool, ctx, {
      patientId: 1,
      documentType: "medical-necessity",
      additionalContext: "patient has nutritional concerns",
    });

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.documentId).toBe(77);
      expect(result.data.content).toMatch(/Dear/);
    }

    const userMessage = askClaudeMock.mock.calls[0][1];
    expect(userMessage).toContain("Jane Doe");
    expect(userMessage).toContain("diabetes");
    expect(userMessage).toContain("nutritional concerns");

    const savedArgs = storageMock.createGeneratedDocument.mock.calls[0][0];
    expect(savedArgs.title).toContain("Medical Necessity");
    expect(savedArgs.title).toContain("Jane Doe");
  });

  it("blocks PHI reads with phi.access_denied when the principal lacks phi.read", async () => {
    const unprivileged = makePrincipal({ userId: "no-phi-user", capabilities: [] });
    const result = await runTool(
      generateDocumentTool,
      { principal: unprivileged },
      { patientId: 1, documentType: "medical-necessity" },
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe(ToolErrorCode.PhiAccessDenied);
      expect(result.error.message).toMatch(/phi\.read/);
    }
    // Storage was never touched because the gate failed before the read.
    expect(storageMock.getPatient).not.toHaveBeenCalled();
    expect(askClaudeMock).not.toHaveBeenCalled();
  });

  it("blocks doc persistence with phi.access_denied when the principal has read but not write", async () => {
    storageMock.getPatient.mockResolvedValue({
      id: 1,
      firstName: "Jane",
      lastName: "Doe",
      dateOfBirth: "1960-01-01",
    });
    storageMock.getMedicalHistory.mockResolvedValue(null);
    storageMock.getTreatmentPlansByPatient.mockResolvedValue([]);
    askClaudeMock.mockResolvedValue("Generated content.");

    const readOnly = makePrincipal({ userId: "ro-user", capabilities: ["phi.read"] });
    const result = await runTool(
      generateDocumentTool,
      { principal: readOnly },
      { patientId: 1, documentType: "medical-necessity" },
    );

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.code).toBe(ToolErrorCode.PhiAccessDenied);
    // Reads happened (audit will show), but no write was attempted.
    expect(storageMock.getPatient).toHaveBeenCalled();
    expect(storageMock.createGeneratedDocument).not.toHaveBeenCalled();
  });

  it("writes audit rows for each PHI access on the happy path", async () => {
    storageMock.getPatient.mockResolvedValue({
      id: 1,
      firstName: "Jane",
      lastName: "Doe",
      dateOfBirth: "1960-01-01",
    });
    storageMock.getMedicalHistory.mockResolvedValue({});
    storageMock.getTreatmentPlansByPatient.mockResolvedValue([]);
    askClaudeMock.mockResolvedValue("Generated.");
    storageMock.createGeneratedDocument.mockResolvedValue({ id: 1 });

    await runTool(generateDocumentTool, ctx, {
      patientId: 1,
      documentType: "medical-necessity",
    });

    // Three reads (patient, medical_history, treatment_plans) + one write
    // (generated_document). Each PHI op writes its own audit row.
    expect(storageMock.createAuditLog).toHaveBeenCalledTimes(4);
    const actions = storageMock.createAuditLog.mock.calls.map((c) => c[0].action);
    expect(actions).toEqual(["phi.read", "phi.read", "phi.read", "phi.create"]);
    // Each row is flagged as PHI access.
    for (const call of storageMock.createAuditLog.mock.calls) {
      expect(call[0].phiAccessed).toBe(true);
    }
  });
});

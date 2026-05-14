import { describe, it, expect, vi, beforeEach } from "vitest";

const storageMock = vi.hoisted(() => ({
  getPatient: vi.fn(),
  getMedicalHistory: vi.fn(),
  getTreatmentPlansByPatient: vi.fn(),
  createGeneratedDocument: vi.fn(),
  createAuditLog: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("../storage", () => ({ storage: storageMock }));

import { phiService, PhiAccessDeniedError } from "./phi";
import { makePrincipal } from "../tools/types";

const phiReader = makePrincipal({
  userId: "staff-1",
  email: "staff@clinic",
  capabilities: ["phi.read", "phi.write"],
});

const phiReaderOnly = makePrincipal({
  userId: "ro-1",
  capabilities: ["phi.read"],
});

const noPhi = makePrincipal({ userId: "marketing-agent", capabilities: [] });

beforeEach(() => {
  vi.clearAllMocks();
  storageMock.createAuditLog.mockResolvedValue(undefined);
});

describe("PhiService.getPatient", () => {
  it("returns the patient and writes an allowed audit row when capability is present", async () => {
    storageMock.getPatient.mockResolvedValue({ id: 42, firstName: "Jane" });

    const patient = await phiService.getPatient(phiReader, 42);

    expect(patient).toMatchObject({ id: 42 });
    expect(storageMock.createAuditLog).toHaveBeenCalledOnce();
    const row = storageMock.createAuditLog.mock.calls[0][0];
    expect(row).toMatchObject({
      userId: "staff-1",
      action: "phi.read",
      resourceType: "patient",
      resourceId: "42",
      patientId: 42,
      phiAccessed: true,
    });
    expect(row.details.allowed).toBe(true);
  });

  it("throws PhiAccessDeniedError + writes a denied audit row when capability is missing", async () => {
    await expect(phiService.getPatient(noPhi, 42)).rejects.toBeInstanceOf(PhiAccessDeniedError);

    // The denied access still leaves a trail.
    expect(storageMock.createAuditLog).toHaveBeenCalledOnce();
    const row = storageMock.createAuditLog.mock.calls[0][0];
    expect(row.action).toBe("phi.read_denied");
    expect(row.details.allowed).toBe(false);
    expect(row.details.reason).toMatch(/phi\.read/);

    // Storage was never queried for the actual patient.
    expect(storageMock.getPatient).not.toHaveBeenCalled();
  });

  it("does not let an audit-log failure mask the data return", async () => {
    storageMock.getPatient.mockResolvedValue({ id: 99 });
    storageMock.createAuditLog.mockRejectedValueOnce(new Error("audit table down"));
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const patient = await phiService.getPatient(phiReader, 99);
    expect(patient).toMatchObject({ id: 99 });
    // The failure was logged so operators see it.
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });
});

describe("PhiService.createGeneratedDocument", () => {
  it("requires phi.write — read-only callers are blocked", async () => {
    await expect(
      phiService.createGeneratedDocument(phiReaderOnly, {
        patientId: 7,
        documentType: "medical-necessity",
        title: "x",
        content: "y",
        metadata: {},
      } as any),
    ).rejects.toBeInstanceOf(PhiAccessDeniedError);

    const row = storageMock.createAuditLog.mock.calls[0][0];
    expect(row.action).toBe("phi.write_denied");
    expect(storageMock.createGeneratedDocument).not.toHaveBeenCalled();
  });

  it("creates the document and writes a phi.create audit row when allowed", async () => {
    storageMock.createGeneratedDocument.mockResolvedValue({ id: 5, patientId: 7 });

    const result = await phiService.createGeneratedDocument(phiReader, {
      patientId: 7,
      documentType: "medical-necessity",
      title: "Medical Necessity - Jane Doe",
      content: "Letter body",
      metadata: {},
    } as any);

    expect(result.id).toBe(5);
    const row = storageMock.createAuditLog.mock.calls[0][0];
    expect(row).toMatchObject({
      action: "phi.create",
      resourceType: "generated_document",
      patientId: 7,
    });
  });
});

describe("hasCapability deny-by-default", () => {
  it("treats a principal with no `capabilities` field as fully denied", async () => {
    // Construct a Principal without going through makePrincipal — mimics a
    // future code path that builds a Principal incorrectly. Default deny.
    const broken: any = { userId: "broken" };
    await expect(phiService.getPatient(broken, 1)).rejects.toBeInstanceOf(PhiAccessDeniedError);
  });
});

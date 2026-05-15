import { describe, it, expect, vi, beforeEach } from "vitest";

const storageMock = vi.hoisted(() => ({
  getPatient: vi.fn(),
  getMedicalHistory: vi.fn(),
  getTreatmentPlansByPatient: vi.fn(),
  getPatientInsurance: vi.fn(),
  createGeneratedDocument: vi.fn(),
  createPatient: vi.fn(),
  // Identity-resolution path uses these. Default to undefined so
  // createPatient falls through to creating a new person.
  findPersonByEmail: vi.fn(),
  findPersonByPhone: vi.fn(),
  findPersonByNameDob: vi.fn(),
  findPersonByExternalId: vi.fn(),
  getPerson: vi.fn(),
  createPerson: vi.fn(),
  linkPersonExternalId: vi.fn(),
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

describe("PhiService tenant filter", () => {
  const tenantA = makePrincipal({
    userId: "staff-a",
    tenantId: "tenant-a",
    capabilities: ["phi.read", "phi.write"],
  });
  const tenantB = makePrincipal({
    userId: "staff-b",
    tenantId: "tenant-b",
    capabilities: ["phi.read", "phi.write"],
  });

  it("returns the row when the patient's tenant matches the principal's tenant", async () => {
    storageMock.getPatient.mockResolvedValue({ id: 1, tenantId: "tenant-a", firstName: "Jane" });
    const result = await phiService.getPatient(tenantA, 1);
    expect(result).toMatchObject({ id: 1, firstName: "Jane" });
  });

  it("returns undefined (treats as not-found) when the patient is in a different tenant", async () => {
    // The row exists in storage, but it belongs to tenant-b.
    storageMock.getPatient.mockResolvedValue({ id: 1, tenantId: "tenant-a", firstName: "Jane" });
    const result = await phiService.getPatient(tenantB, 1);
    expect(result).toBeUndefined();
  });

  it("passes through rows without a tenantId (legacy / not-yet-backfilled)", async () => {
    // Backward compatibility: rows that pre-date the tenant column have
    // tenantId === null. The filter lets them through so the upgrade can
    // be rolled out without a flag day.
    storageMock.getPatient.mockResolvedValue({ id: 7, tenantId: null, firstName: "Legacy" });
    const result = await phiService.getPatient(tenantA, 7);
    expect(result).toMatchObject({ id: 7, firstName: "Legacy" });
  });

  it("does NOT filter when the principal has no tenantId (single-tenant mode)", async () => {
    // Principal without tenantId = single-tenant deployment; no filter applied.
    const noTenant = makePrincipal({ userId: "x", capabilities: ["phi.read"] });
    storageMock.getPatient.mockResolvedValue({ id: 9, tenantId: "tenant-a", firstName: "X" });
    const result = await phiService.getPatient(noTenant, 9);
    expect(result).toMatchObject({ id: 9 });
  });

  it("filters arrays element-wise (cross-tenant rows dropped)", async () => {
    // Storage returned a mixed bag — only the matching tenant's row should
    // remain. This is the realistic shape from queries like
    // getTreatmentPlansByPatient or getPatientInsurance.
    storageMock.getPatientInsurance.mockResolvedValue([
      { id: 1, tenantId: "tenant-a", providerName: "Yours" },
      { id: 2, tenantId: "tenant-b", providerName: "Theirs" },
      { id: 3, tenantId: null, providerName: "Legacy passthrough" },
    ]);
    const result = await phiService.getPatientInsurance(tenantA, 1);
    expect(result).toHaveLength(2); // tenant-a + null-tenant pass; tenant-b dropped
    expect(result.map((r: any) => r.id).sort()).toEqual([1, 3]);
  });

  it("denies null-tenant rows when STRICT_TENANT_ISOLATION=true", async () => {
    const original = process.env.STRICT_TENANT_ISOLATION;
    process.env.STRICT_TENANT_ISOLATION = "true";
    try {
      storageMock.getPatient.mockResolvedValue({ id: 7, tenantId: null, firstName: "Legacy" });
      const result = await phiService.getPatient(tenantA, 7);
      // In strict mode the legacy passthrough is gone: null-tenant rows
      // look like cross-tenant and are filtered out.
      expect(result).toBeUndefined();
    } finally {
      if (original !== undefined) process.env.STRICT_TENANT_ISOLATION = original;
      else delete process.env.STRICT_TENANT_ISOLATION;
    }
  });

  it("injects the principal's tenantId on createPatient", async () => {
    storageMock.getPerson.mockResolvedValue(undefined);
    storageMock.findPersonByEmail.mockResolvedValue(undefined);
    storageMock.findPersonByPhone.mockResolvedValue(undefined);
    storageMock.findPersonByNameDob.mockResolvedValue(undefined);
    storageMock.createPerson.mockResolvedValue({ id: "new-person-uuid", tenantId: "tenant-a" });
    storageMock.createPatient.mockResolvedValue({ id: 42, tenantId: "tenant-a" });

    await phiService.createPatient(tenantA, {
      firstName: "New",
      lastName: "Patient",
      email: "new@example.com",
      dateOfBirth: "1990-01-01",
    } as any);

    const patientArgs = storageMock.createPatient.mock.calls[0][0];
    expect(patientArgs.tenantId).toBe("tenant-a");
    const personArgs = storageMock.createPerson.mock.calls[0][0];
    expect(personArgs.tenantId).toBe("tenant-a");
  });
});

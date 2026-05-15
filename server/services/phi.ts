import { storage } from "../storage";
import { hasCapability, type Principal } from "../tools/types";
import { resolveOrCreatePerson } from "./identity";

// ── PhiService ───────────────────────────────────────────────────────────
// Single gate for every PHI read/write in the application. Two guarantees:
//
//   1. Pre-flight capability check: if the caller doesn't have the
//      capability, we DON'T touch storage. A denied row goes to the audit
//      log so attempted unauthorized access is visible.
//
//   2. Post-hoc audit row: every successful PHI access creates an
//      `audit_logs` entry tied to the principal, the resource, and the
//      operation. This is independent of the URL-pattern PHI audit
//      middleware — that one logs HTTP requests; this one logs DATA access,
//      which is more precise (a tool that reads PHI internally without an
//      HTTP route still gets logged).
//
// Per fusion_crm doctrine: `ops` → `phi` imports are forbidden anywhere
// EXCEPT through this service. Today we don't enforce that at the import
// level (Drizzle uses one schema), but consumers should treat this as the
// only legitimate route to PHI data.

export class PhiAccessDeniedError extends Error {
  readonly code = "phi.access_denied" as const;
  constructor(
    message: string,
    readonly resourceType: string,
    readonly resourceId?: string | number | null,
  ) {
    super(message);
    this.name = "PhiAccessDeniedError";
  }
}

interface AuditOpts {
  principal: Principal;
  action: string;
  resourceType: string;
  resourceId?: string | number | null;
  patientId?: number | null;
  allowed: boolean;
  reason?: string;
}

async function writeAuditRow(opts: AuditOpts): Promise<void> {
  // Fire-and-don't-await would be a bug here — we want the row written before
  // the caller sees the result (so a crash mid-flight doesn't leave a PHI
  // read undocumented). The DB call is cheap; await it.
  try {
    await storage.createAuditLog({
      userId: opts.principal.userId,
      userEmail: opts.principal.email ?? null,
      action: `phi.${opts.action}`,
      resourceType: opts.resourceType,
      resourceId: opts.resourceId != null ? String(opts.resourceId) : null,
      patientId: opts.patientId ?? null,
      ipAddress: null,
      userAgent: null,
      details: { allowed: opts.allowed, reason: opts.reason },
      phiAccessed: true,
    });
  } catch (err) {
    // We never let an audit-write failure mask the real outcome. Log loudly
    // so operators see it, but still return the data the caller asked for.
    console.error("PhiService: failed to write audit row", err);
  }
}

async function requireRead(principal: Principal, resourceType: string, resourceId?: number | string | null): Promise<void> {
  if (!hasCapability(principal, "phi.read")) {
    await writeAuditRow({
      principal,
      action: "read_denied",
      resourceType,
      resourceId: resourceId ?? null,
      patientId: typeof resourceId === "number" ? resourceId : null,
      allowed: false,
      reason: "missing phi.read capability",
    });
    throw new PhiAccessDeniedError(
      "Caller does not have phi.read capability",
      resourceType,
      resourceId,
    );
  }
}

async function requireWrite(principal: Principal, resourceType: string, resourceId?: number | string | null): Promise<void> {
  if (!hasCapability(principal, "phi.write")) {
    await writeAuditRow({
      principal,
      action: "write_denied",
      resourceType,
      resourceId: resourceId ?? null,
      patientId: typeof resourceId === "number" ? resourceId : null,
      allowed: false,
      reason: "missing phi.write capability",
    });
    throw new PhiAccessDeniedError(
      "Caller does not have phi.write capability",
      resourceType,
      resourceId,
    );
  }
}

// ── Read helpers ─────────────────────────────────────────────────────────
// Each method is a one-pattern wrapper: capability check → storage call →
// audit row. The repetition is intentional — explicit gates are easier to
// audit than a metaprogrammed dispatcher. Adding a new PHI resource means
// one more pair (read + write) here, nothing else.

// Tenant filter: if the principal has a tenantId set, any row returned
// from storage must match it. Mismatched rows are mapped to `undefined`
// so callers (and the HTTP layer) cannot distinguish "doesn't exist" from
// "exists in another tenant" — that's the leak we're preventing.
//
// Arrays are filtered element-wise. If the principal has no tenantId
// (single-tenant deployment, or legacy backfill not yet done), the
// filter is a no-op — backward compatible.
//
// Strict mode (set `STRICT_TENANT_ISOLATION=true` after the backfill has
// run on every environment) tightens the policy: rows with no `tenantId`
// are treated as cross-tenant — i.e. denied — instead of passed through.
// Flip this when you're confident every legacy row has been assigned.

function isStrictTenantIsolation(): boolean {
  return process.env.STRICT_TENANT_ISOLATION === "true";
}

function rowTenantOk(rowTenant: unknown, callerTenant: string): boolean {
  if (rowTenant === callerTenant) return true;
  // null/undefined tenant on the row = legacy. In strict mode that's a deny.
  if (rowTenant == null) return !isStrictTenantIsolation();
  return false;
}

function filterByTenant<T>(principal: Principal, value: T): T {
  if (!principal.tenantId) return value;
  if (value === null || value === undefined) return value;
  if (Array.isArray(value)) {
    return value.filter((row: any) => {
      if (!row || typeof row !== "object") return true;
      return rowTenantOk(row.tenantId, principal.tenantId!);
    }) as unknown as T;
  }
  if (typeof value === "object") {
    if (!rowTenantOk((value as any).tenantId, principal.tenantId)) {
      return undefined as unknown as T;
    }
  }
  return value;
}

async function gatedRead<T>(
  principal: Principal,
  resourceType: string,
  resourceId: number | null,
  patientId: number | null,
  fetch: () => Promise<T>,
): Promise<T> {
  await requireRead(principal, resourceType, resourceId);
  const result = await fetch();
  const filtered = filterByTenant(principal, result);
  await writeAuditRow({
    principal,
    action: "read",
    resourceType,
    resourceId,
    patientId,
    allowed: true,
  });
  return filtered;
}

async function gatedWrite<T>(
  principal: Principal,
  resourceType: string,
  patientId: number | null,
  resourceId: number | string | null,
  action: string,
  perform: () => Promise<T>,
): Promise<T> {
  await requireWrite(principal, resourceType, resourceId);
  const result = await perform();
  await writeAuditRow({
    principal,
    action,
    resourceType,
    resourceId,
    patientId,
    allowed: true,
  });
  return result;
}

// ── Patient ──────────────────────────────────────────────────────────────

export async function getPatient(principal: Principal, id: number) {
  return gatedRead(principal, "patient", id, id, () => storage.getPatient(id));
}

export async function getPatientWithDetails(principal: Principal, id: number) {
  return gatedRead(principal, "patient_with_details", id, id, () =>
    storage.getPatientWithDetails(id),
  );
}

export async function getPatients(principal: Principal) {
  // List access: no specific patientId; resourceId is null.
  return gatedRead(principal, "patient_list", null, null, () => storage.getPatients());
}

export async function createPatient(
  principal: Principal,
  data: Parameters<typeof storage.createPatient>[0],
) {
  return gatedWrite(principal, "patient", null, null, "create", async () => {
    // Resolve canonical identity before creating the patient row so the
    // new record carries `person_uid` from the start. If the same human
    // already exists (as a prior patient or a lead), they share the UUID.
    // Identity resolution carries the principal's tenant so the resulting
    // person row is scoped to the same clinic.
    const { person } = await resolveOrCreatePerson({
      firstName: (data as any).firstName ?? null,
      lastName: (data as any).lastName ?? null,
      email: (data as any).email ?? null,
      phone: (data as any).phone ?? null,
      dateOfBirth: (data as any).dateOfBirth ?? null,
      source: "patient",
      tenantId: principal.tenantId ?? null,
    });
    const created = await storage.createPatient({
      ...(data as any),
      personUid: person.id,
      // Inject the caller's tenant so the new row is bound to their
      // clinic. Cross-tenant access by future readers is denied by the
      // tenant filter in gatedRead.
      tenantId: principal.tenantId ?? null,
    });
    return created;
  });
}

export async function updatePatient(
  principal: Principal,
  id: number,
  data: Parameters<typeof storage.updatePatient>[1],
) {
  return gatedWrite(principal, "patient", id, id, "update", () =>
    storage.updatePatient(id, data),
  );
}

// ── Medical history ──────────────────────────────────────────────────────

export async function getMedicalHistory(principal: Principal, patientId: number) {
  return gatedRead(principal, "medical_history", patientId, patientId, () =>
    storage.getMedicalHistory(patientId),
  );
}

// ── Dental info ──────────────────────────────────────────────────────────

export async function getDentalInfo(principal: Principal, patientId: number) {
  return gatedRead(principal, "dental_info", patientId, patientId, () =>
    storage.getDentalInfo(patientId),
  );
}

// ── Facial evaluation ────────────────────────────────────────────────────

export async function getFacialEvaluation(principal: Principal, patientId: number) {
  return gatedRead(principal, "facial_evaluation", patientId, patientId, () =>
    storage.getFacialEvaluation(patientId),
  );
}

// ── Insurance ────────────────────────────────────────────────────────────

export async function getPatientInsurance(principal: Principal, patientId: number) {
  return gatedRead(principal, "insurance", patientId, patientId, () =>
    storage.getPatientInsurance(patientId),
  );
}

// ── Treatment plans ──────────────────────────────────────────────────────

export async function getTreatmentPlansByPatient(principal: Principal, patientId: number) {
  return gatedRead(principal, "treatment_plans", patientId, patientId, () =>
    storage.getTreatmentPlansByPatient(patientId),
  );
}

export async function getTreatmentPlan(principal: Principal, id: number) {
  return gatedRead(principal, "treatment_plan", id, null, () => storage.getTreatmentPlan(id));
}

// ── Clinical notes ───────────────────────────────────────────────────────

export async function getPatientNotes(principal: Principal, patientId: number) {
  return gatedRead(principal, "clinical_notes", patientId, patientId, () =>
    storage.getPatientNotes(patientId),
  );
}

// ── Appointments ─────────────────────────────────────────────────────────

export async function getAppointments(
  principal: Principal,
  filters?: Parameters<typeof storage.getAppointments>[0],
) {
  const patientId = filters?.patientId ?? null;
  return gatedRead(principal, "appointments", patientId, patientId, () =>
    storage.getAppointments(filters),
  );
}

// ── Consent forms ────────────────────────────────────────────────────────

export async function getConsentFormsByPatient(principal: Principal, patientId: number) {
  return gatedRead(principal, "consent_forms", patientId, patientId, () =>
    storage.getConsentFormsByPatient(patientId),
  );
}

// ── Prior authorizations ─────────────────────────────────────────────────

export async function getPriorAuthorizations(
  principal: Principal,
  filters?: Parameters<typeof storage.getPriorAuthorizations>[0],
) {
  const patientId = filters?.patientId ?? null;
  return gatedRead(principal, "prior_authorizations", patientId, patientId, () =>
    storage.getPriorAuthorizations(filters),
  );
}

// ── Generated documents (write) ──────────────────────────────────────────

export async function createGeneratedDocument(
  principal: Principal,
  data: Parameters<typeof storage.createGeneratedDocument>[0],
) {
  const patientId = (data as any)?.patientId ?? null;
  return gatedWrite(principal, "generated_document", patientId, null, "create", () =>
    storage.createGeneratedDocument(data),
  );
}

// ── Patient deletion ─────────────────────────────────────────────────────

export async function deletePatient(principal: Principal, id: number) {
  return gatedWrite(principal, "patient", id, id, "delete", () =>
    storage.deletePatient(id),
  );
}

// ── Insurance ────────────────────────────────────────────────────────────

export async function createInsurance(
  principal: Principal,
  data: Parameters<typeof storage.createInsurance>[0],
) {
  const patientId = (data as any)?.patientId ?? null;
  return gatedWrite(principal, "insurance", patientId, null, "create", () =>
    storage.createInsurance(data),
  );
}

export async function updateInsurance(
  principal: Principal,
  id: number,
  data: Parameters<typeof storage.updateInsurance>[1],
) {
  return gatedWrite(principal, "insurance", null, id, "update", () =>
    storage.updateInsurance(id, data),
  );
}

// ── Treatment plans (write) ──────────────────────────────────────────────

export async function createTreatmentPlan(
  principal: Principal,
  data: Parameters<typeof storage.createTreatmentPlan>[0],
) {
  const patientId = (data as any)?.patientId ?? null;
  return gatedWrite(principal, "treatment_plan", patientId, null, "create", () =>
    storage.createTreatmentPlan(data),
  );
}

export async function updateTreatmentPlan(
  principal: Principal,
  id: number,
  data: Parameters<typeof storage.updateTreatmentPlan>[1],
) {
  return gatedWrite(principal, "treatment_plan", null, id, "update", () =>
    storage.updateTreatmentPlan(id, data),
  );
}

// ── Consent forms (write) ────────────────────────────────────────────────

export async function createConsentForm(
  principal: Principal,
  data: Parameters<typeof storage.createConsentForm>[0],
) {
  const patientId = (data as any)?.patientId ?? null;
  return gatedWrite(principal, "consent_form", patientId, null, "create", () =>
    storage.createConsentForm(data),
  );
}

export const phiService = {
  // Read
  getPatient,
  getPatientWithDetails,
  getPatients,
  getMedicalHistory,
  getDentalInfo,
  getFacialEvaluation,
  getPatientInsurance,
  getTreatmentPlansByPatient,
  getTreatmentPlan,
  getPatientNotes,
  getAppointments,
  getConsentFormsByPatient,
  getPriorAuthorizations,
  // Write
  createPatient,
  updatePatient,
  deletePatient,
  createInsurance,
  updateInsurance,
  createTreatmentPlan,
  updateTreatmentPlan,
  createConsentForm,
  createGeneratedDocument,
};

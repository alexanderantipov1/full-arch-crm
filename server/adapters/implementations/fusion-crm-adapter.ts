/**
 * full-arch-crm — FusionCrmAdapter
 * ─────────────────────────────────
 * HTTP client adapter that calls the fusion_crm REST API
 * (alexanderantipov1/fusion_crm)
 *
 * Architecture:
 *   full-arch-crm (universal SaaS dental PMS)
 *       └── FusionCrmAdapter  ←→  fusion_crm REST API (Fusion Dental Corp)
 *
 * Onboarding a new DSO: create a new file here, implement DatabaseAdapter,
 * register in registry.ts. Zero core code changes needed.
 *
 * HIPAA: All PHI calls write to audit trail BEFORE data is returned.
 *        Audit failures block PHI access in production (BAA mode).
 *
 * Env vars consumed:
 *   FUSION_CRM_URL         — base URL, e.g. http://localhost:8000
 *   FUSION_CRM_API_KEY     — Bearer token for API authentication
 *   FUSION_TENANT_ID       — tenant UUID sent as X-Tenant-ID
 *   FUSION_CRM_TIMEOUT_MS  — request timeout in ms (default 10000)
 */

import type {
  CanonicalPatient,
  CanonicalPatientSummary,
  CanonicalMedicalHistory,
  CanonicalInsurance,
  CanonicalEligibilityResult,
  CanonicalAppointment,
  CanonicalTreatmentPlan,
  CanonicalClinicalNote,
  CanonicalClaim,
  CanonicalPriorAuth,
  CanonicalFinancingPlan,
  AnonymizedIntelligencePattern,
  AdapterHealthStatus,
  PatientListOptions,
  PatientListResult,
  AppointmentListOptions,
  ClaimListOptions,
  PhiAccessContext,
  PhiAuditEntry,
  AdapterType,
} from "../types";

import type { DatabaseAdapter, CdtCodeResult, EobPosting } from "../interface";
import { SchemaTranslator, FUSION_CRM_MAPPING } from "../translator";

// ─── Config ──────────────────────────────────────────────────────────────────

export interface FusionCrmAdapterConfig {
  baseUrl: string;          // e.g. http://localhost:8000
  apiKey: string;           // Bearer token
  tenantId: string;
  timeoutMs?: number;       // default 10000
  retryAttempts?: number;   // default 3
}

// ─── UUID v4 generator (no external deps) ────────────────────────────────────

function uuidv4(): string {
  // Use crypto.randomUUID when available (Node 16+, all modern browsers)
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  // Fallback for older runtimes
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

// ─── Adapter ─────────────────────────────────────────────────────────────────

export class FusionCrmAdapter implements DatabaseAdapter {
  readonly adapterType = "fusion_crm" as const;
  readonly tenantId: string;

  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly timeoutMs: number;
  private readonly retryAttempts: number;
  private readonly translator: SchemaTranslator;

  constructor(config: FusionCrmAdapterConfig, tenantId: string) {
    this.tenantId = tenantId;
    this.baseUrl = config.baseUrl.replace(/\/$/, "");
    this.apiKey = config.apiKey;
    this.timeoutMs = config.timeoutMs ?? 10000;
    this.retryAttempts = config.retryAttempts ?? 3;
    this.translator = new SchemaTranslator(FUSION_CRM_MAPPING);

    if (!this.baseUrl) {
      throw new Error(
        "[FusionCrmAdapter] FUSION_CRM_URL is not set. " +
        "Set it in your environment (e.g. FUSION_CRM_URL=http://localhost:8000)."
      );
    }
    if (!this.apiKey) {
      throw new Error(
        "[FusionCrmAdapter] FUSION_CRM_API_KEY is not set. " +
        "Add FUSION_CRM_API_KEY=<your-key> to your .env file."
      );
    }
  }

  // ─── Core HTTP client ────────────────────────────────────────────────────

  private async request<T>(
    method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
    path: string,
    options: {
      body?: unknown;
      phiContext?: PhiAccessContext;
      query?: Record<string, string | number | boolean | undefined>;
      /** Expected top-level keys for shape validation. All must be present. */
      expectedShape?: string[];
    } = {}
  ): Promise<T> {
    const url = new URL(`${this.baseUrl}${path}`);
    if (options.query) {
      for (const [k, v] of Object.entries(options.query)) {
        if (v !== undefined) url.searchParams.set(k, String(v));
      }
    }

    const requestId = uuidv4();

    const headers: Record<string, string> = {
      "Authorization": `Bearer ${this.apiKey}`,
      "Content-Type": "application/json",
      "X-Tenant-ID": this.tenantId,
      "X-Request-ID": requestId,
      "X-Source": "full-arch-crm",
    };

    if (options.phiContext) {
      headers["X-Phi-Purpose"] = options.phiContext.purpose;
      headers["X-Phi-Requested-By"] = options.phiContext.requestedBy;
      headers["X-Trace-Id"] = options.phiContext.traceId;
      headers["X-Baa-Verified"] = "true";
    }

    let lastError: Error | null = null;

    for (let attempt = 1; attempt <= this.retryAttempts; attempt++) {
      const startMs = Date.now();
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

        let response: Response;
        try {
          response = await fetch(url.toString(), {
            method,
            headers,
            body: options.body ? JSON.stringify(options.body) : undefined,
            signal: controller.signal,
          });
        } catch (networkErr) {
          clearTimeout(timeoutId);
          const elapsed = Date.now() - startMs;
          const isAbort = (networkErr as Error).name === "AbortError";
          console.error(
            `[FusionCrmAdapter] ${method} ${path} FAILED after ${elapsed}ms` +
            ` (req=${requestId}, attempt=${attempt}/${this.retryAttempts})` +
            ` — ${isAbort ? `timeout (>${this.timeoutMs}ms)` : (networkErr as Error).message}`
          );
          if (isAbort) {
            throw new FusionApiNetworkError(
              path,
              `fusion_crm is unreachable: request timed out after ${this.timeoutMs}ms. ` +
              `Verify FUSION_CRM_URL=${this.baseUrl} is accessible and the service is running.`
            );
          }
          throw new FusionApiNetworkError(
            path,
            `fusion_crm is unreachable: ${(networkErr as Error).message}. ` +
            `Verify FUSION_CRM_URL=${this.baseUrl} is accessible and the service is running.`
          );
        }

        clearTimeout(timeoutId);
        const elapsed = Date.now() - startMs;

        // ── Request logging ───────────────────────────────────────────────
        console.log(
          `[FusionCrmAdapter] ${method} ${path} → ${response.status} (${elapsed}ms, req=${requestId})`
        );

        if (!response.ok) {
          if (response.status === 404) return null as unknown as T;
          if (response.status === 401 || response.status === 403) {
            throw new FusionApiAuthError(path, response.status, response.statusText);
          }
          if (response.status === 429 && attempt < this.retryAttempts) {
            const retryAfter = parseInt(response.headers.get("Retry-After") ?? "2");
            console.warn(
              `[FusionCrmAdapter] Rate limited on ${method} ${path} — ` +
              `retrying in ${retryAfter}s (attempt ${attempt}/${this.retryAttempts})`
            );
            await sleep(retryAfter * 1000);
            continue;
          }
          const errBody = await response.json().catch(() => ({ message: response.statusText })) as { message: string; code?: string };
          throw new FusionApiRequestError(path, response.status, errBody.message, errBody.code);
        }

        if (response.status === 204) return undefined as unknown as T;

        const data = await response.json() as T;

        // ── Response shape validation ─────────────────────────────────────
        if (options.expectedShape && options.expectedShape.length > 0 && data !== null && typeof data === "object") {
          const dataObj = data as Record<string, unknown>;
          const missingKeys = options.expectedShape.filter((k) => !(k in dataObj));
          if (missingKeys.length > 0) {
            console.warn(
              `[FusionCrmAdapter] ${method} ${path} — unexpected response shape. ` +
              `Expected keys: [${options.expectedShape.join(", ")}], ` +
              `missing: [${missingKeys.join(", ")}]. ` +
              `Raw response: ${JSON.stringify(data)}`
            );
            throw new FusionApiShapeError(
              path,
              `Response from fusion_crm is missing expected fields: [${missingKeys.join(", ")}]. ` +
              `This may indicate an API version mismatch. ` +
              `Check that FUSION_CRM_URL=${this.baseUrl} points to a compatible fusion_crm instance.`
            );
          }
        }

        return data;

      } catch (err) {
        if (err instanceof FusionApiAuthError) throw err;
        if (err instanceof FusionApiNetworkError) throw err;
        if (err instanceof FusionApiShapeError) throw err;
        if (err instanceof FusionApiRequestError && err.status < 500) throw err;
        lastError = err as Error;
        if (attempt < this.retryAttempts) {
          const delay = Math.min(1000 * Math.pow(2, attempt - 1), 8000);
          const elapsed = Date.now() - startMs;
          console.warn(
            `[FusionCrmAdapter] Retry ${attempt}/${this.retryAttempts}: ` +
            `${method} ${path} failed after ${elapsed}ms — ${(err as Error).message}`
          );
          await sleep(delay);
        }
      }
    }

    throw lastError ?? new Error(`[FusionCrmAdapter] Request failed: ${method} ${path}`);
  }

  // ─── Health ──────────────────────────────────────────────────────────────

  async healthCheck(): Promise<AdapterHealthStatus> {
    const start = Date.now();
    try {
      await this.request<{ status: string }>("GET", "/healthz");
      return {
        healthy: true,
        adapterType: this.adapterType,
        tenantId: this.tenantId,
        latencyMs: Date.now() - start,
        lastCheckedAt: new Date(),
      };
    } catch (err) {
      return {
        healthy: false,
        adapterType: this.adapterType,
        tenantId: this.tenantId,
        latencyMs: Date.now() - start,
        errorMessage: (err as Error).message,
        lastCheckedAt: new Date(),
      };
    }
  }

  // ─── Patients ────────────────────────────────────────────────────────────

  async listPatients(options: PatientListOptions = {}): Promise<PatientListResult> {
    const raw = await this.request<{ patients: unknown[]; total: number; cursor?: string; hasMore?: boolean }>(
      "GET", "/api/v1/patients",
      {
        query: {
          cursor: options.cursor,
          limit: options.limit ?? 50,
          search: options.search,
          stage: options.stage,
          insuranceType: options.insuranceType,
          activeTreatmentPlan: options.activeTreatmentPlan,
        },
        expectedShape: ["patients", "total"],
      }
    );
    const items: CanonicalPatientSummary[] = (raw?.patients ?? []).map(
      (p) => this.translator.toCanonicalPatientSummary(p as Record<string, unknown>)
    );
    return {
      items,
      total: raw?.total ?? items.length,
      nextCursor: raw?.cursor,
      hasMore: raw?.hasMore ?? false,
    };
  }

  async getPatient(personUid: string, phiContext: PhiAccessContext): Promise<CanonicalPatient | null> {
    await this._auditPhi(personUid, phiContext, ["demographics", "clinical_summary", "contact_info"]);
    const raw = await this.request<Record<string, unknown>>("GET", `/api/v1/patients/${personUid}`, { phiContext });
    if (!raw) return null;
    return this.translator.toCanonicalPatient(raw) as CanonicalPatient;
  }

  async searchPatients(query: string, limit = 20): Promise<CanonicalPatientSummary[]> {
    const raw = await this.request<{ patients: unknown[] }>(
      "GET", "/api/v1/patients/search",
      {
        query: { q: query, limit },
        expectedShape: ["patients"],
      }
    );
    return (raw?.patients ?? []).map((p) => this.translator.toCanonicalPatientSummary(p as Record<string, unknown>));
  }

  async createPatient(
    data: Omit<CanonicalPatient, "personUid" | "createdAt" | "updatedAt" | "sourceAdapter" | "dataFreshness">,
    phiContext: PhiAccessContext
  ): Promise<CanonicalPatient> {
    await this._auditPhi("new", phiContext, ["demographics", "contact_info"]);
    const raw = await this.request<Record<string, unknown>>("POST", "/api/v1/patients", { body: data, phiContext });
    return this.translator.toCanonicalPatient(raw) as CanonicalPatient;
  }

  async updatePatient(
    personUid: string,
    updates: Partial<Pick<CanonicalPatient, "firstName" | "lastName" | "email" | "phone" | "address" | "emergencyContact">>,
    phiContext: PhiAccessContext
  ): Promise<CanonicalPatient> {
    await this._auditPhi(personUid, phiContext, Object.keys(updates));
    const raw = await this.request<Record<string, unknown>>("PATCH", `/api/v1/patients/${personUid}`, { body: updates, phiContext });
    return this.translator.toCanonicalPatient(raw) as CanonicalPatient;
  }

  // ─── Medical History ─────────────────────────────────────────────────────

  async getMedicalHistory(personUid: string, phiContext: PhiAccessContext): Promise<CanonicalMedicalHistory | null> {
    await this._auditPhi(personUid, phiContext, ["conditions", "allergies", "medications", "surgeries"]);
    const raw = await this.request<Record<string, unknown>>("GET", `/api/v1/patients/${personUid}/medical-history`, { phiContext });
    if (!raw) return null;
    return this._toMedicalHistory(personUid, raw);
  }

  async upsertMedicalHistory(data: CanonicalMedicalHistory, phiContext: PhiAccessContext): Promise<CanonicalMedicalHistory> {
    await this._auditPhi(data.personUid, phiContext, ["conditions", "allergies", "medications"]);
    const raw = await this.request<Record<string, unknown>>("PUT", `/api/v1/patients/${data.personUid}/medical-history`, { body: data, phiContext });
    return this._toMedicalHistory(data.personUid, raw);
  }

  // ─── Insurance ───────────────────────────────────────────────────────────

  async getInsurance(personUid: string, phiContext: PhiAccessContext): Promise<CanonicalInsurance[]> {
    await this._auditPhi(personUid, phiContext, ["insurance.policyNumber", "insurance.groupNumber"]);
    const raw = await this.request<{ plans: unknown[] }>(
      "GET", `/api/v1/patients/${personUid}/insurance`,
      { phiContext, expectedShape: ["plans"] }
    );
    return (raw?.plans ?? []).map((p) => this.translator.toCanonicalInsurance(p as Record<string, unknown>) as CanonicalInsurance);
  }

  async checkEligibility(personUid: string, procedureCodes: string[], phiContext: PhiAccessContext): Promise<CanonicalEligibilityResult> {
    await this._auditPhi(personUid, phiContext, ["insurance.eligibility"]);
    const raw = await this.request<Record<string, unknown>>(
      "POST", `/api/v1/patients/${personUid}/eligibility`,
      { body: { procedureCodes }, phiContext }
    );
    return this._toEligibilityResult(personUid, raw);
  }

  // ─── Appointments ────────────────────────────────────────────────────────

  async listAppointments(options: AppointmentListOptions): Promise<CanonicalAppointment[]> {
    const raw = await this.request<{ appointments: unknown[] }>(
      "GET", "/api/v1/appointments",
      {
        query: {
          personUid: options.personUid,
          from: options.dateFrom?.toISOString(),
          to: options.dateTo?.toISOString(),
          status: options.status,
          providerId: options.providerId,
          limit: options.limit ?? 50,
        },
        expectedShape: ["appointments"],
      }
    );
    return (raw?.appointments ?? []).map((a) => this.translator.toCanonicalAppointment(a as Record<string, unknown>) as CanonicalAppointment);
  }

  async getAppointment(appointmentId: string): Promise<CanonicalAppointment | null> {
    const raw = await this.request<Record<string, unknown>>("GET", `/api/v1/appointments/${appointmentId}`);
    if (!raw) return null;
    return this.translator.toCanonicalAppointment(raw) as CanonicalAppointment;
  }

  async createAppointment(data: Omit<CanonicalAppointment, "appointmentId" | "createdAt" | "updatedAt" | "sourceAdapter">): Promise<CanonicalAppointment> {
    const raw = await this.request<Record<string, unknown>>("POST", "/api/v1/appointments", { body: data });
    return this.translator.toCanonicalAppointment(raw) as CanonicalAppointment;
  }

  async updateAppointment(appointmentId: string, updates: Partial<Pick<CanonicalAppointment, "startTime" | "endTime" | "status" | "notes" | "providerId" | "chair">>): Promise<CanonicalAppointment> {
    const raw = await this.request<Record<string, unknown>>("PATCH", `/api/v1/appointments/${appointmentId}`, { body: updates });
    return this.translator.toCanonicalAppointment(raw) as CanonicalAppointment;
  }

  async cancelAppointment(appointmentId: string, reason?: string): Promise<void> {
    await this.request<void>("DELETE", `/api/v1/appointments/${appointmentId}`, { body: reason ? { reason } : undefined });
  }

  // ─── Treatment Plans ─────────────────────────────────────────────────────

  async getTreatmentPlans(personUid: string, phiContext: PhiAccessContext): Promise<CanonicalTreatmentPlan[]> {
    await this._auditPhi(personUid, phiContext, ["treatment_plans"]);
    const raw = await this.request<{ plans: unknown[] }>(
      "GET", `/api/v1/patients/${personUid}/treatment-plans`,
      { phiContext, expectedShape: ["plans"] }
    );
    return (raw?.plans ?? []).map((p) => this.translator.toCanonicalTreatmentPlan(p as Record<string, unknown>) as CanonicalTreatmentPlan);
  }

  async getTreatmentPlan(planId: string, phiContext: PhiAccessContext): Promise<CanonicalTreatmentPlan | null> {
    await this._auditPhi(phiContext.patientId ?? "unknown", phiContext, ["treatment_plan"]);
    const raw = await this.request<Record<string, unknown>>("GET", `/api/v1/treatment-plans/${planId}`, { phiContext });
    if (!raw) return null;
    return this.translator.toCanonicalTreatmentPlan(raw) as CanonicalTreatmentPlan;
  }

  async createTreatmentPlan(data: Omit<CanonicalTreatmentPlan, "planId" | "createdAt" | "updatedAt" | "sourceAdapter">, phiContext: PhiAccessContext): Promise<CanonicalTreatmentPlan> {
    await this._auditPhi(data.personUid, phiContext, ["treatment_plan"]);
    const raw = await this.request<Record<string, unknown>>("POST", "/api/v1/treatment-plans", { body: data, phiContext });
    return this.translator.toCanonicalTreatmentPlan(raw) as CanonicalTreatmentPlan;
  }

  async updateTreatmentPlan(planId: string, updates: Partial<CanonicalTreatmentPlan>, phiContext: PhiAccessContext): Promise<CanonicalTreatmentPlan> {
    await this._auditPhi(updates.personUid ?? phiContext.patientId ?? "unknown", phiContext, Object.keys(updates));
    const raw = await this.request<Record<string, unknown>>("PATCH", `/api/v1/treatment-plans/${planId}`, { body: updates, phiContext });
    return this.translator.toCanonicalTreatmentPlan(raw) as CanonicalTreatmentPlan;
  }

  // ─── Clinical Notes ──────────────────────────────────────────────────────

  async getClinicalNotes(personUid: string, phiContext: PhiAccessContext): Promise<CanonicalClinicalNote[]> {
    await this._auditPhi(personUid, phiContext, ["clinical_notes"]);
    const raw = await this.request<{ notes: unknown[] }>(
      "GET", `/api/v1/patients/${personUid}/clinical-notes`,
      { phiContext, expectedShape: ["notes"] }
    );
    return (raw?.notes ?? []).map((n) => this.translator.toCanonicalClinicalNote(n as Record<string, unknown>) as CanonicalClinicalNote);
  }

  async saveClinicalNote(data: Omit<CanonicalClinicalNote, "noteId" | "createdAt" | "updatedAt" | "sourceAdapter">, phiContext: PhiAccessContext): Promise<CanonicalClinicalNote> {
    await this._auditPhi(data.personUid, phiContext, ["clinical_note.soap"]);
    const raw = await this.request<Record<string, unknown>>("POST", `/api/v1/patients/${data.personUid}/clinical-notes`, { body: data, phiContext });
    return this.translator.toCanonicalClinicalNote(raw) as CanonicalClinicalNote;
  }

  // ─── CDT Codes ───────────────────────────────────────────────────────────

  async searchCdtCodes(query: string, limit = 20): Promise<CdtCodeResult[]> {
    const raw = await this.request<{ codes: CdtCodeResult[] }>(
      "GET", "/api/v1/cdt-codes",
      {
        query: { q: query, limit },
        expectedShape: ["codes"],
      }
    );
    return raw?.codes ?? [];
  }

  // ─── Billing / Claims ────────────────────────────────────────────────────

  async listClaims(options: ClaimListOptions): Promise<CanonicalClaim[]> {
    const raw = await this.request<{ claims: unknown[] }>(
      "GET", "/api/v1/claims",
      {
        query: {
          personUid: options.personUid,
          status: options.status,
          from: options.dateFrom?.toISOString(),
          to: options.dateTo?.toISOString(),
          cdtCode: options.cdtCode,
          limit: options.limit ?? 50,
        },
        expectedShape: ["claims"],
      }
    );
    return (raw?.claims ?? []).map((c) => this.translator.toCanonicalClaim(c as Record<string, unknown>) as CanonicalClaim);
  }

  async getClaim(claimId: string): Promise<CanonicalClaim | null> {
    const raw = await this.request<Record<string, unknown>>("GET", `/api/v1/claims/${claimId}`);
    if (!raw) return null;
    return this.translator.toCanonicalClaim(raw) as CanonicalClaim;
  }

  async createClaim(data: Omit<CanonicalClaim, "claimId" | "createdAt" | "updatedAt" | "sourceAdapter">, phiContext: PhiAccessContext): Promise<CanonicalClaim> {
    await this._auditPhi(data.personUid, phiContext, ["claim"]);
    const raw = await this.request<Record<string, unknown>>("POST", "/api/v1/claims", { body: data, phiContext });
    return this.translator.toCanonicalClaim(raw) as CanonicalClaim;
  }

  async updateClaim(claimId: string, updates: Partial<Pick<CanonicalClaim, "claimStatus" | "allowedAmount" | "paidAmount" | "patientPortion" | "denialReason" | "appealStatus" | "paidDate">>): Promise<CanonicalClaim> {
    const raw = await this.request<Record<string, unknown>>("PATCH", `/api/v1/claims/${claimId}`, { body: updates });
    return this.translator.toCanonicalClaim(raw) as CanonicalClaim;
  }

  async postEob(claimId: string, eob: EobPosting, phiContext: PhiAccessContext): Promise<CanonicalClaim> {
    await this._auditPhi(phiContext.patientId ?? "unknown", phiContext, ["claim.eob_posting"]);
    const raw = await this.request<Record<string, unknown>>("POST", `/api/v1/claims/${claimId}/eob`, { body: eob, phiContext });
    return this.translator.toCanonicalClaim(raw) as CanonicalClaim;
  }

  // ─── Prior Authorization ─────────────────────────────────────────────────

  async getPriorAuths(personUid: string, phiContext: PhiAccessContext): Promise<CanonicalPriorAuth[]> {
    await this._auditPhi(personUid, phiContext, ["prior_auths"]);
    const raw = await this.request<{ auths: unknown[] }>(
      "GET", `/api/v1/patients/${personUid}/prior-auths`,
      { phiContext, expectedShape: ["auths"] }
    );
    return (raw?.auths ?? []).map((a) => this._toPriorAuth(a as Record<string, unknown>));
  }

  async createPriorAuth(data: Omit<CanonicalPriorAuth, "authId">, phiContext: PhiAccessContext): Promise<CanonicalPriorAuth> {
    await this._auditPhi(data.personUid, phiContext, ["prior_auth"]);
    const raw = await this.request<Record<string, unknown>>("POST", `/api/v1/patients/${data.personUid}/prior-auths`, { body: data, phiContext });
    return this._toPriorAuth(raw);
  }

  async updatePriorAuth(authId: string, updates: Partial<CanonicalPriorAuth>): Promise<CanonicalPriorAuth> {
    const raw = await this.request<Record<string, unknown>>("PATCH", `/api/v1/prior-auths/${authId}`, { body: updates });
    return this._toPriorAuth(raw);
  }

  // ─── Financing ───────────────────────────────────────────────────────────

  async getFinancingPlans(personUid: string, phiContext: PhiAccessContext): Promise<CanonicalFinancingPlan[]> {
    await this._auditPhi(personUid, phiContext, ["financing", "financing.accountNumber"]);
    const raw = await this.request<{ plans: unknown[] }>(
      "GET", `/api/v1/patients/${personUid}/financing`,
      { phiContext, expectedShape: ["plans"] }
    );
    return (raw?.plans ?? []).map((p) => this._toFinancingPlan(p as Record<string, unknown>));
  }

  async createFinancingPlan(data: Omit<CanonicalFinancingPlan, "planId">, phiContext: PhiAccessContext): Promise<CanonicalFinancingPlan> {
    await this._auditPhi(data.personUid, phiContext, ["financing"]);
    const raw = await this.request<Record<string, unknown>>("POST", `/api/v1/patients/${data.personUid}/financing`, { body: data, phiContext });
    return this._toFinancingPlan(raw);
  }

  // ─── Intelligence ────────────────────────────────────────────────────────

  async pushIntelligence(pattern: AnonymizedIntelligencePattern): Promise<void> {
    await this.request<void>("POST", "/api/v1/intelligence/patterns", { body: pattern });
  }

  async queryIntelligence(patternType: string, query: Record<string, unknown>): Promise<AnonymizedIntelligencePattern[]> {
    const raw = await this.request<{ patterns: AnonymizedIntelligencePattern[] }>(
      "POST", "/api/v1/intelligence/query",
      {
        body: { patternType, query },
        expectedShape: ["patterns"],
      }
    );
    return raw?.patterns ?? [];
  }

  // ─── HIPAA Audit ─────────────────────────────────────────────────────────

  async logPhiAccess(entry: Omit<PhiAuditEntry, "id" | "timestamp">): Promise<void> {
    try {
      await this.request<void>("POST", "/api/v1/audit/phi-access", { body: { ...entry, timestamp: new Date().toISOString() } });
    } catch (err) {
      console.error("[FusionCrmAdapter] HIPAA audit log write FAILED:", err);
      // In production BAA mode: block PHI access on audit failure
      if (process.env.NODE_ENV === "production" && process.env.ANTHROPIC_BAA_SIGNED === "true") {
        throw new Error(`[HIPAA] PHI access audit log failure — blocking PHI access: ${(err as Error).message}`);
      }
    }
  }

  async getAuditLog(options: { tenantId: string; from: Date; to: Date; patientId?: string }, phiContext: PhiAccessContext): Promise<PhiAuditEntry[]> {
    if (phiContext.purpose !== "audit") throw new Error("[HIPAA] getAuditLog requires purpose=audit");
    const raw = await this.request<{ entries: PhiAuditEntry[] }>(
      "GET", "/api/v1/audit/phi-access",
      {
        query: {
          tenantId: options.tenantId,
          from: options.from.toISOString(),
          to: options.to.toISOString(),
          patientId: options.patientId,
        },
        phiContext,
        expectedShape: ["entries"],
      }
    );
    return raw?.entries ?? [];
  }

  // ─── Private: inline translators for types not yet in SchemaTranslator ───

  private _toMedicalHistory(personUid: string, raw: Record<string, unknown>): CanonicalMedicalHistory {
    return {
      personUid,
      tenantId: (raw.tenant_id ?? this.tenantId) as string,
      conditions: this._arr(raw.conditions ?? raw.medical_conditions),
      allergies: this._arr(raw.allergies),
      medications: this._arr(raw.medications ?? raw.current_medications),
      surgeries: this._arr(raw.surgeries ?? raw.surgical_history),
      smokingStatus: raw.smoking_status as string | undefined,
      alcoholUse: raw.alcohol_use as string | undefined,
      bloodPressure: raw.blood_pressure as string | undefined,
      weight: raw.weight as string | undefined,
      height: raw.height as string | undefined,
      lastPhysicalExam: raw.last_physical_exam ? new Date(raw.last_physical_exam as string) : undefined,
      notes: raw.notes as string | undefined,
      updatedAt: raw.updated_at ? new Date(raw.updated_at as string) : new Date(),
    };
  }

  private _toEligibilityResult(personUid: string, raw: Record<string, unknown>): CanonicalEligibilityResult {
    const coverageDetails = (raw.coverage_details ?? raw) as Record<string, unknown>;
    const procedureCoverageMap: Record<string, { cdtCode: string; covered: boolean; coveragePercent: number; requiresPriorAuth: boolean; limitations?: string }> = {};
    const coverageArr = raw.procedure_coverage as Array<{ code?: string; cdtCode?: string; covered?: boolean; coveragePercent?: number; coverage_percent?: number; requiresPriorAuth?: boolean; requires_auth?: boolean; limitations?: string }> | undefined;
    if (Array.isArray(coverageArr)) {
      for (const pc of coverageArr) {
        const code = pc.code ?? pc.cdtCode ?? "";
        procedureCoverageMap[code] = {
          cdtCode: code,
          covered: Boolean(pc.covered),
          coveragePercent: Number(pc.coveragePercent ?? pc.coverage_percent ?? 0),
          requiresPriorAuth: Boolean(pc.requiresPriorAuth ?? pc.requires_auth),
          limitations: pc.limitations,
        };
      }
    }
    return {
      personUid,
      tenantId: this.tenantId,
      checkedAt: new Date(),
      status: (raw.status ?? (raw.eligible ? "active" : "inactive")) as "active" | "inactive" | "unknown",
      remainingBenefit: Number(raw.remaining_benefit ?? raw.deductible_remaining ?? 0),
      deductibleMet: Number(raw.deductible_met ?? 0),
      coverageDetails,
      procedureCoverageMap,
    };
  }

  private _toPriorAuth(raw: Record<string, unknown>): CanonicalPriorAuth {
    return {
      authId: (raw.auth_id ?? raw.id ?? "") as string,
      personUid: (raw.person_uid ?? raw.patient_id ?? "") as string,
      tenantId: (raw.tenant_id ?? this.tenantId) as string,
      treatmentPlanId: raw.treatment_plan_id as string | undefined,
      authType: (raw.auth_type ?? raw.type ?? "predetermination") as string,
      status: (raw.status ?? "submitted") as CanonicalPriorAuth["status"],
      submissionDate: raw.submission_date ? new Date(raw.submission_date as string) : undefined,
      responseDate: raw.response_date ? new Date(raw.response_date as string) : undefined,
      expirationDate: raw.expiration_date ? new Date(raw.expiration_date as string) : undefined,
      authNumber: raw.auth_number as string | undefined,
      requestedProcedures: (raw.requested_procedures ?? raw.procedure_codes ?? {}) as Record<string, unknown>,
      approvedProcedures: raw.approved_procedures as Record<string, unknown> | undefined,
      denialReason: raw.denial_reason as string | undefined,
      medicalNecessityLetter: raw.medical_necessity_letter as string | undefined,
      notes: raw.notes as string | undefined,
    };
  }

  private _toFinancingPlan(raw: Record<string, unknown>): CanonicalFinancingPlan {
    return {
      planId: (raw.plan_id ?? raw.id ?? "") as string,
      personUid: (raw.person_uid ?? raw.patient_id ?? "") as string,
      tenantId: (raw.tenant_id ?? this.tenantId) as string,
      treatmentPlanId: raw.treatment_plan_id as string | undefined,
      provider: (raw.provider ?? raw.lender ?? raw.financing_type ?? "") as string,
      applicationStatus: (raw.application_status ?? raw.status ?? "pending") as CanonicalFinancingPlan["applicationStatus"],
      approvedAmount: raw.approved_amount ? Number(raw.approved_amount) : undefined,
      interestRate: raw.interest_rate ? Number(raw.interest_rate) : undefined,
      termMonths: raw.term_months ? Number(raw.term_months) : undefined,
      monthlyPayment: raw.monthly_payment ? Number(raw.monthly_payment) : undefined,
      downPayment: raw.down_payment ? Number(raw.down_payment) : undefined,
      approvalDate: raw.approval_date ? new Date(raw.approval_date as string) : undefined,
      expirationDate: raw.expiration_date ? new Date(raw.expiration_date as string) : undefined,
      accountNumber: raw.account_number as string | undefined,
      notes: raw.notes as string | undefined,
    };
  }

  private _arr(value: unknown): string[] {
    if (!value) return [];
    if (Array.isArray(value)) return value.map(String);
    if (typeof value === "string") {
      try { return JSON.parse(value); } catch { return [value]; }
    }
    return [];
  }

  // ─── Private: HIPAA audit helper ─────────────────────────────────────────

  private async _auditPhi(
    patientId: string,
    phiContext: PhiAccessContext,
    fieldsAccessed: string[]
  ): Promise<void> {
    await this.logPhiAccess({
      tenantId: this.tenantId,
      patientId,
      accessedBy: phiContext.requestedBy,
      purpose: phiContext.purpose,
      fieldsAccessed,
      sourceAdapter: this.adapterType as AdapterType,
      traceId: phiContext.traceId,
    });
  }
}

// ─── Error types ─────────────────────────────────────────────────────────────

export class FusionApiError extends Error {
  constructor(public readonly path: string, message: string) {
    super(`[FusionCrmAdapter] ${path}: ${message}`);
    this.name = "FusionApiError";
  }
}

export class FusionApiAuthError extends FusionApiError {
  constructor(path: string, public readonly status: number, message: string) {
    super(path, `Auth error (${status}): ${message}`);
    this.name = "FusionApiAuthError";
  }
}

export class FusionApiRequestError extends FusionApiError {
  constructor(path: string, public readonly status: number, message: string, public readonly code?: string) {
    super(path, `HTTP ${status}${code ? ` [${code}]` : ""}: ${message}`);
    this.name = "FusionApiRequestError";
  }
}

export class FusionApiNetworkError extends FusionApiError {
  constructor(path: string, message: string) {
    super(path, message);
    this.name = "FusionApiNetworkError";
  }
}

export class FusionApiShapeError extends FusionApiError {
  constructor(path: string, message: string) {
    super(path, message);
    this.name = "FusionApiShapeError";
  }
}

// ─── Utility ─────────────────────────────────────────────────────────────────

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

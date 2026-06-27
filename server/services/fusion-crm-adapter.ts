/**
 * full-arch-crm — FusionCrmAdapter
 *
 * Implements DatabaseAdapter for Fusion Dental's fusion_crm backend.
 * This is the HTTP client that talks to the fusion_crm REST API (/api/v1/).
 *
 * Config via environment variables:
 *   FUSION_CRM_URL        — base URL (e.g. http://localhost:8000)
 *   FUSION_API_KEY        — X-Fusion-API-Key header value
 *   FUSION_TENANT_ID      — X-Tenant-ID header value
 *
 * When FUSION_CRM_URL is not set, isMockMode() returns true and the adapter
 * returns stub data so full-arch-crm can run locally without a real backend.
 *
 * Any other clinic that wants to use full-arch-crm builds their own adapter
 * (e.g. EagleSoftAdapter, DentrixAdapter) implementing the same DatabaseAdapter interface.
 */

import type {
  AnonymizedPattern,
  AppealInput,
  AppointmentSlot,
  AvailabilitySlot,
  BookAppointmentInput,
  CDTCode,
  Claim,
  ClaimStatusUpdate,
  ClinicalNote,
  CreateClaimInput,
  DatabaseAdapter,
  EligibilityResult,
  InsuranceCoverage,
  IntelligenceQueryResult,
  PagedResult,
  PatientListItem,
  PatientSnapshot,
  SoapNote,
  TreatmentHistory,
} from './database-adapter.js';

import {
  AdapterAuthError,
  AdapterNotFoundError,
  AdapterUnavailableError,
  DatabaseAdapterError,
} from './database-adapter.js';

// ── Config ─────────────────────────────────────────────────────────────────────

interface FusionCrmConfig {
  baseUrl: string;
  apiKey: string;
  tenantId: string;
  timeoutMs?: number;
  phiAccessReasonPrefix?: string;
}

function loadConfig(): FusionCrmConfig | null {
  const baseUrl = process.env.FUSION_CRM_URL;
  const apiKey = process.env.FUSION_API_KEY;
  const tenantId = process.env.FUSION_TENANT_ID;

  if (!baseUrl || !apiKey || !tenantId) return null;

  return {
    baseUrl: baseUrl.replace(/\/$/, ''),
    apiKey,
    tenantId,
    timeoutMs: Number(process.env.FUSION_CRM_TIMEOUT_MS ?? 10000),
    phiAccessReasonPrefix: process.env.FUSION_PHI_REASON_PREFIX ?? 'full_arch_crm',
  };
}

// ── HTTP helpers ───────────────────────────────────────────────────────────────

async function httpRequest<T>(
  config: FusionCrmConfig,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  path: string,
  options: {
    params?: Record<string, string | undefined>;
    body?: unknown;
    reason?: string;
  } = {},
): Promise<T> {
  const url = new URL(`${config.baseUrl}/api/v1${path}`);

  if (options.params) {
    for (const [k, v] of Object.entries(options.params)) {
      if (v !== undefined) url.searchParams.set(k, v);
    }
  }

  const headers: Record<string, string> = {
    'X-Fusion-API-Key': config.apiKey,
    'X-Tenant-ID': config.tenantId,
    'X-Request-Source': 'full_arch_crm',
    'Content-Type': 'application/json',
  };

  if (options.reason) {
    headers['X-PHI-Access-Reason'] = `${config.phiAccessReasonPrefix}.${options.reason}`;
  }

  const res = await fetch(url.toString(), {
    method,
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    signal: AbortSignal.timeout(config.timeoutMs ?? 10000),
  });

  if (!res.ok) {
    let detail: unknown;
    try { detail = await res.json(); } catch { detail = await res.text(); }

    if (res.status === 401) throw new AdapterAuthError('fusion_crm', detail);
    if (res.status === 404) throw new DatabaseAdapterError('fusion_crm', 404, 'Not found', detail);
    if (res.status === 503) throw new AdapterUnavailableError('fusion_crm', detail);
    throw new DatabaseAdapterError('fusion_crm', res.status, `HTTP ${res.status}`, detail);
  }

  return res.json() as Promise<T>;
}

// ── Camel-case converters ──────────────────────────────────────────────────────

function toCamel<T extends Record<string, unknown>>(snake: Record<string, unknown>): T {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(snake)) {
    const camel = k.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
    out[camel] = v;
  }
  return out as T;
}

function toSnake<T extends Record<string, unknown>>(camel: Record<string, unknown>): T {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(camel)) {
    const snake = k.replace(/([A-Z])/g, '_$1').toLowerCase();
    out[snake] = v;
  }
  return out as T;
}

// ── Stub data (mock mode) ──────────────────────────────────────────────────────

const STUB_PATIENT: PatientListItem = {
  personUid: '00000000-0000-0000-0000-000000000001',
  displayName: 'John D.',
  ageBand: '45-54',
  insuranceType: 'ppo',
  lastVisitDate: '2026-03-15',
  activeTreatmentPlan: true,
  scenarioTag: 'implant_consult',
};

const STUB_SNAPSHOT: PatientSnapshot = {
  personUid: '00000000-0000-0000-0000-000000000001',
  fullName: 'John Doe',
  dob: '1975-04-15',
  phone: '+15551234567',
  email: 'john.doe@example.com',
  address: { line1: '123 Main St', city: 'San Diego', state: 'CA', zip: '92101' },
  insurance: {
    personUid: '00000000-0000-0000-0000-000000000001',
    primaryPayer: 'Delta Dental of California',
    memberId: 'DD123456',
    groupId: 'GRP789',
    planType: 'ppo',
    copay: 20,
    deductibleRemaining: 500,
  },
  phiAccessLogged: true,
  reason: 'mock',
};

// ── FusionCrmAdapter ──────────────────────────────────────────────────────────

export class FusionCrmAdapter implements DatabaseAdapter {
  readonly adapterId = 'fusion_crm';
  private config: FusionCrmConfig | null;

  constructor(config?: FusionCrmConfig) {
    this.config = config ?? loadConfig();
  }

  isMockMode(): boolean {
    return this.config === null;
  }

  private get cfg(): FusionCrmConfig {
    if (!this.config) {
      throw new DatabaseAdapterError(
        'fusion_crm',
        503,
        'FusionCrmAdapter is in mock mode — set FUSION_CRM_URL, FUSION_API_KEY, FUSION_TENANT_ID',
      );
    }
    return this.config;
  }

  private get<T>(path: string, params?: Record<string, string | undefined>, reason?: string) {
    return httpRequest<T>(this.cfg, 'GET', path, { params, reason });
  }

  private post<T>(path: string, body: unknown, reason?: string) {
    return httpRequest<T>(this.cfg, 'POST', path, { body, reason });
  }

  private put<T>(path: string, body: unknown, reason?: string) {
    return httpRequest<T>(this.cfg, 'PUT', path, { body, reason });
  }

  private delete<T>(path: string) {
    return httpRequest<T>(this.cfg, 'DELETE', path);
  }

  // ── Patients ──────────────────────────────────────────────────────────────

  async getPatients(cursor?: string, limit = 50): Promise<PagedResult<PatientListItem>> {
    if (this.isMockMode()) {
      return { items: [STUB_PATIENT], total: 1, cursor: null };
    }
    const res = await this.get<{ items: Record<string, unknown>[]; total: number; cursor?: string }>(
      '/patients',
      { cursor, limit: String(limit) },
    );
    return {
      items: res.items.map(toCamel<PatientListItem>),
      total: res.total,
      cursor: res.cursor,
    };
  }

  async getPatient(personUid: string, reason: string): Promise<PatientSnapshot> {
    if (this.isMockMode()) return { ...STUB_SNAPSHOT, personUid, reason };
    const res = await this.get<Record<string, unknown>>(
      `/patients/${personUid}/snapshot`,
      { reason },
      reason,
    );
    return toCamel<PatientSnapshot>(res);
  }

  async getPatientTreatmentHistory(personUid: string): Promise<TreatmentHistory> {
    if (this.isMockMode()) {
      return {
        personUid,
        visits: [{
          visitDate: '2026-03-15',
          providerId: '00000000-0000-0000-0000-000000000099',
          procedures: [{ cdtCode: 'D0150', description: 'Comprehensive Oral Evaluation', fee: 120, status: 'paid' }],
          clinicalNotesAvailable: false,
        }],
      };
    }
    const res = await this.get<Record<string, unknown>>(`/patients/${personUid}/treatment-history`);
    return toCamel<TreatmentHistory>(res);
  }

  async searchPatients(query: string, limit = 25): Promise<PagedResult<PatientListItem>> {
    if (this.isMockMode()) return { items: [], total: 0 };
    const res = await this.get<{ items: Record<string, unknown>[]; total: number }>(
      '/patients/search',
      { q: query, limit: String(limit) },
    );
    return { items: res.items.map(toCamel<PatientListItem>), total: res.total };
  }

  async createPatient(data: Omit<PatientSnapshot, 'personUid' | 'phiAccessLogged' | 'reason'>): Promise<{ personUid: string }> {
    if (this.isMockMode()) return { personUid: crypto.randomUUID() };
    return this.post<{ personUid: string }>('/patients', toSnake(data as Record<string, unknown>));
  }

  async updatePatient(personUid: string, data: Partial<PatientSnapshot>): Promise<void> {
    if (this.isMockMode()) return;
    await this.put(`/patients/${personUid}/profile`, toSnake(data as Record<string, unknown>));
  }

  // ── Appointments ──────────────────────────────────────────────────────────

  async getAppointments(date: string, locationId?: string): Promise<AppointmentSlot[]> {
    if (this.isMockMode()) return [];
    const res = await this.get<{ slots: Record<string, unknown>[] }>(
      '/appointments',
      { date, location_id: locationId },
    );
    return res.slots.map(toCamel<AppointmentSlot>);
  }

  async getUpcomingAppointments(personUid: string, limit = 10): Promise<AppointmentSlot[]> {
    if (this.isMockMode()) return [];
    const res = await this.get<{ slots: Record<string, unknown>[] }>(
      '/appointments/upcoming',
      { person_uid: personUid, limit: String(limit) },
    );
    return res.slots.map(toCamel<AppointmentSlot>);
  }

  async getAvailability(providerId: string, dateFrom: string, dateTo: string): Promise<AvailabilitySlot[]> {
    if (this.isMockMode()) return [];
    const res = await this.get<{ available_slots: Record<string, unknown>[] }>(
      '/appointments/availability',
      { provider_id: providerId, date_from: dateFrom, date_to: dateTo },
    );
    return res.available_slots.map(toCamel<AvailabilitySlot>);
  }

  async getAppointment(appointmentId: string): Promise<AppointmentSlot | null> {
    if (this.isMockMode()) return null;
    try {
      const res = await this.get<Record<string, unknown>>(`/appointments/${appointmentId}`);
      return toCamel<AppointmentSlot>(res);
    } catch (e) {
      if (e instanceof DatabaseAdapterError && e.statusCode === 404) return null;
      throw e;
    }
  }

  async bookAppointment(data: BookAppointmentInput): Promise<{ appointmentId: string }> {
    if (this.isMockMode()) return { appointmentId: crypto.randomUUID() };
    const res = await this.post<{ appointment_id: string }>('/appointments', toSnake(data as Record<string, unknown>));
    return { appointmentId: res.appointment_id };
  }

  async updateAppointment(appointmentId: string, data: Partial<BookAppointmentInput & { status: string }>): Promise<void> {
    if (this.isMockMode()) return;
    await this.put(`/appointments/${appointmentId}`, toSnake(data as Record<string, unknown>));
  }

  async cancelAppointment(appointmentId: string): Promise<void> {
    if (this.isMockMode()) return;
    await this.delete(`/appointments/${appointmentId}`);
  }

  // ── Clinical Notes ────────────────────────────────────────────────────────

  async getClinicalNotes(personUid: string, limit = 20): Promise<ClinicalNote[]> {
    if (this.isMockMode()) return [];
    const res = await this.get<Record<string, unknown>[]>(
      '/clinical-notes',
      { person_uid: personUid, limit: String(limit) },
      'view_clinical_notes',
    );
    return res.map(toCamel<ClinicalNote>);
  }

  async getClinicalNote(noteId: string): Promise<ClinicalNote | null> {
    if (this.isMockMode()) return null;
    try {
      const res = await this.get<Record<string, unknown>>(`/clinical-notes/${noteId}`, {}, 'view_clinical_note');
      return toCamel<ClinicalNote>(res);
    } catch (e) {
      if (e instanceof DatabaseAdapterError && e.statusCode === 404) return null;
      throw e;
    }
  }

  async saveScribeOutput(
    personUid: string,
    appointmentId: string,
    soap: SoapNote,
    cdtCodes: string[],
    options: { aiModel?: string; providerId?: string } = {},
  ): Promise<{ noteId: string }> {
    if (this.isMockMode()) return { noteId: crypto.randomUUID() };
    const res = await this.post<{ note_id: string }>(
      '/clinical-notes',
      {
        person_uid: personUid,
        appointment_id: appointmentId,
        provider_id: options.providerId,
        visit_date: new Date().toISOString().slice(0, 10),
        note_type: 'soap',
        subjective: soap.subjective,
        objective: soap.objective,
        assessment: soap.assessment,
        plan: soap.plan,
        ai_generated: true,
        ai_model: options.aiModel ?? 'unknown',
        provider_approved: false,
        source: 'full_arch_crm.ai_scribe',
        cdt_codes: cdtCodes,
      },
      'ai_scribe.write_note',
    );
    return { noteId: res.note_id };
  }

  async searchCdtCodes(query: string, limit = 25): Promise<CDTCode[]> {
    if (this.isMockMode()) return [];
    const res = await this.get<{ items: Record<string, unknown>[] }>(
      '/cdt-codes',
      { search: query, limit: String(limit) },
    );
    return res.items.map(toCamel<CDTCode>);
  }

  async getCdtCode(code: string): Promise<CDTCode | null> {
    if (this.isMockMode()) return null;
    try {
      const res = await this.get<Record<string, unknown>>(`/cdt-codes/${code}`);
      return toCamel<CDTCode>(res);
    } catch (e) {
      if (e instanceof DatabaseAdapterError && e.statusCode === 404) return null;
      throw e;
    }
  }

  // ── Insurance & Claims ────────────────────────────────────────────────────

  async getInsurance(personUid: string): Promise<InsuranceCoverage | null> {
    if (this.isMockMode()) return null;
    try {
      const res = await this.get<Record<string, unknown>>(
        `/insurance/${personUid}`,
        {},
        'view_insurance',
      );
      return toCamel<InsuranceCoverage>(res);
    } catch (e) {
      if (e instanceof DatabaseAdapterError && e.statusCode === 404) return null;
      throw e;
    }
  }

  async checkEligibility(personUid: string, procedureCodes: string[], appointmentDate?: string): Promise<EligibilityResult> {
    if (this.isMockMode()) {
      return {
        personUid,
        eligible: true,
        planType: 'ppo',
        benefitRemaining: 1750,
        procedureCoverage: Object.fromEntries(procedureCodes.map(c => [c, { covered: true, estimatedBenefitPct: 0.8 }])),
        verifiedAt: new Date().toISOString(),
        notes: 'Mock eligibility — FUSION_CRM_URL not set',
      };
    }
    const res = await this.post<Record<string, unknown>>(
      '/insurance/eligibility-check',
      { person_uid: personUid, procedure_codes: procedureCodes, appointment_date: appointmentDate },
      'eligibility_check',
    );
    return toCamel<EligibilityResult>(res);
  }

  async getClaims(personUid: string, status?: string): Promise<Claim[]> {
    if (this.isMockMode()) return [];
    const res = await this.get<Record<string, unknown>[]>(
      '/insurance/claims',
      { person_uid: personUid, status },
    );
    return res.map(toCamel<Claim>);
  }

  async getClaim(claimId: string): Promise<Claim | null> {
    if (this.isMockMode()) return null;
    try {
      const res = await this.get<Record<string, unknown>>(`/insurance/claims/${claimId}`);
      return toCamel<Claim>(res);
    } catch (e) {
      if (e instanceof DatabaseAdapterError && e.statusCode === 404) return null;
      throw e;
    }
  }

  async getEobs(dateFrom: string, dateTo: string): Promise<Claim[]> {
    if (this.isMockMode()) return [];
    const res = await this.get<Record<string, unknown>[]>(
      '/insurance/claims/eobs',
      { date_from: dateFrom, date_to: dateTo },
    );
    return res.map(toCamel<Claim>);
  }

  async createClaim(data: CreateClaimInput): Promise<{ claimId: string }> {
    if (this.isMockMode()) return { claimId: crypto.randomUUID() };
    const res = await this.post<{ claim_id: string }>(
      '/insurance/claims',
      toSnake(data as Record<string, unknown>),
      'submit_claim',
    );
    return { claimId: res.claim_id };
  }

  async updateClaimStatus(claimId: string, update: ClaimStatusUpdate): Promise<void> {
    if (this.isMockMode()) return;
    await this.put(
      `/insurance/claims/${claimId}/status`,
      toSnake(update as Record<string, unknown>),
      'eob_posting',
    );
  }

  async fileAppeal(claimId: string, data: AppealInput): Promise<{ appealId: string }> {
    if (this.isMockMode()) return { appealId: crypto.randomUUID() };
    const res = await this.post<{ appeal_id: string }>(
      `/insurance/claims/${claimId}/appeal`,
      toSnake(data as Record<string, unknown>),
      'file_appeal',
    );
    return { appealId: res.appeal_id };
  }

  // ── Intelligence ──────────────────────────────────────────────────────────

  async pushIntelligence(patterns: AnonymizedPattern[]): Promise<{ accepted: number; rejected: number }> {
    if (this.isMockMode()) return { accepted: 0, rejected: 0 };
    const res = await this.post<{ accepted: number; rejected: number }>(
      '/intelligence/ingest',
      { patterns: patterns.map(p => toSnake(p as Record<string, unknown>)) },
    );
    return res;
  }

  async queryIntelligence(category: string, cdtCode?: string, payerType?: string): Promise<IntelligenceQueryResult> {
    if (this.isMockMode()) {
      return { category, patterns: [], confidence: 'low', sourceCount: 0 };
    }
    const res = await this.get<Record<string, unknown>>(
      '/intelligence/query',
      { category, cdt_code: cdtCode, payer_type: payerType },
    );
    return toCamel<IntelligenceQueryResult>(res);
  }
}

// ── Registry ───────────────────────────────────────────────────────────────────

/**
 * FusionCrmAdapterRegistry — maps clinicId → FusionCrmAdapter.
 *
 * In a multi-clinic deployment each clinic has its own credentials.
 * In a single-clinic deployment (the current setup) there is one default adapter.
 *
 * Other adapters for different clinic systems can be registered here too.
 * The key insight: full-arch-crm doesn't care which adapter it's talking to.
 */
class FusionCrmAdapterRegistry {
  private adapters = new Map<string, FusionCrmAdapter>();

  /** Get or create the adapter for a clinic. Uses env vars for default clinic. */
  getAdapter(clinicId = 'default'): FusionCrmAdapter {
    if (!this.adapters.has(clinicId)) {
      if (clinicId === 'default') {
        this.adapters.set('default', new FusionCrmAdapter());
      } else {
        // In multi-clinic: load credentials from DB/secrets by clinicId
        const url = process.env[`FUSION_CRM_URL__${clinicId}`] ?? process.env.FUSION_CRM_URL ?? '';
        const key = process.env[`FUSION_API_KEY__${clinicId}`] ?? process.env.FUSION_API_KEY ?? '';
        const tenantId = process.env[`FUSION_TENANT_ID__${clinicId}`] ?? process.env.FUSION_TENANT_ID ?? '';
        this.adapters.set(clinicId, new FusionCrmAdapter({ baseUrl: url, apiKey: key, tenantId }));
      }
    }
    return this.adapters.get(clinicId)!;
  }

  /** Evict cached adapter (e.g. when clinic rotates their API key). */
  evict(clinicId: string): void {
    this.adapters.delete(clinicId);
  }
}

export const fusionCrmRegistry = new FusionCrmAdapterRegistry();

/** Convenience singleton for single-clinic use. */
export const fusionCrmAdapter = new FusionCrmAdapter();

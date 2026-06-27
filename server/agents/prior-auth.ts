/**
 * Prior Authorization submission agent
 *
 * Submits prior auth requests to Change Healthcare's Prior Auth API.
 * Falls back to mock mode when CHANGE_HEALTHCARE_API_KEY is not set.
 *
 * HIPAA: every submission is recorded via AuditLogger.
 */

import { randomUUID } from "crypto";
import { storage } from "../storage";

// ── Env ──────────────────────────────────────────────────────────────────────

const CHANGE_HEALTHCARE_API_KEY = process.env.CHANGE_HEALTHCARE_API_KEY ?? "";
const CHC_PRIOR_AUTH_BASE =
  "https://api.changehealthcare.com/medicalnetwork/priorauthorization/v1";

// ── Public types ─────────────────────────────────────────────────────────────

export interface PriorAuthParams {
  tenantId:       string;
  patientId:      string;
  procedureCodes: string[];   // e.g. ['D6010', 'D6057']
  diagnosisCodes: string[];   // ICD-10 codes e.g. ['K08.409']
  insurerId:      string;
  providerId:     string;
  treatmentNotes: string;
}

export interface PriorAuthResult {
  authNumber:    string;
  status:        "approved" | "pending" | "denied";
  expiresAt:     string;      // ISO datetime
  approvedCodes: string[];
  requestId:     string;
  submittedAt:   string;
  provider:      "changehealthcare" | "mock";
}

// ── Internal: retry helper (reuse backoff pattern from eligibility-agent) ────

const RETRY_DELAYS_MS = [500, 1000, 2000];

async function fetchWithRetry(
  url: string,
  init: RequestInit,
  attempt = 0,
): Promise<Response> {
  try {
    const res = await fetch(url, init);
    if ((res.status === 429 || res.status >= 500) && attempt < RETRY_DELAYS_MS.length) {
      await sleep(RETRY_DELAYS_MS[attempt]);
      return fetchWithRetry(url, init, attempt + 1);
    }
    return res;
  } catch (err) {
    if (attempt < RETRY_DELAYS_MS.length) {
      await sleep(RETRY_DELAYS_MS[attempt]);
      return fetchWithRetry(url, init, attempt + 1);
    }
    throw err;
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ── Change Healthcare prior auth submission ──────────────────────────────────

interface CHCPriorAuthResponse {
  authorizationNumber?: string;
  statusCode?:          string;
  status?:              string;
  certificationIssueDate?: string;
  certificationExpirationDate?: string;
  approvedCodes?: string[];
  errors?: Array<{ message: string }>;
}

async function submitCHCPriorAuth(params: PriorAuthParams): Promise<PriorAuthResult> {
  const requestId   = randomUUID();
  const submittedAt = new Date().toISOString();

  const requestBody = {
    controlNumber: requestId.replace(/-/g, "").slice(0, 9).toUpperCase(),
    tradingPartnerServiceId: params.insurerId,
    provider: {
      organizationName: "Full Arch CRM Clinic",
      npi:              params.providerId,
    },
    subscriber: {
      memberId: params.patientId,
    },
    requestedServiceType: "Dental",
    serviceLines: params.procedureCodes.map(code => ({
      procedureCode: code,
      diagnosisCodes: params.diagnosisCodes,
      quantity:       "1",
    })),
    requestType:     "Initial",
    certificationAction: "Request",
    additionalNotes: params.treatmentNotes,
  };

  const res = await fetchWithRetry(`${CHC_PRIOR_AUTH_BASE}/requests`, {
    method:  "POST",
    headers: {
      "Authorization": `Bearer ${CHANGE_HEALTHCARE_API_KEY}`,
      "Content-Type":  "application/json",
      "Accept":        "application/json",
    },
    body: JSON.stringify(requestBody),
  });

  if (!res.ok) {
    throw new Error(
      `Change Healthcare prior auth submission failed: ${res.status} ${await res.text()}`,
    );
  }

  const data = await res.json() as CHCPriorAuthResponse;
  return mapCHCPriorAuthResponse(params, requestId, submittedAt, data);
}

function mapCHCPriorAuthResponse(
  params: PriorAuthParams,
  requestId: string,
  submittedAt: string,
  data: CHCPriorAuthResponse,
): PriorAuthResult {
  const statusCode = data.statusCode ?? "A1"; // A1 = Approved, A3 = Pending, A2 = Denied
  const statusMap: Record<string, PriorAuthResult["status"]> = {
    A1: "approved",
    A3: "pending",
    A2: "denied",
  };
  const status = statusMap[statusCode] ?? "pending";

  // Default expiry: 90 days from now if not provided
  const expiresAt =
    data.certificationExpirationDate ??
    new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toISOString();

  return {
    authNumber:    data.authorizationNumber ?? `PA-${requestId.slice(0, 8).toUpperCase()}`,
    status,
    expiresAt,
    approvedCodes: data.approvedCodes ?? (status === "approved" ? params.procedureCodes : []),
    requestId,
    submittedAt,
    provider: "changehealthcare",
  };
}

// ── Mock mode ─────────────────────────────────────────────────────────────────

function buildMockPriorAuth(params: PriorAuthParams): PriorAuthResult {
  const requestId   = randomUUID();
  const submittedAt = new Date().toISOString();
  const expiresAt   = new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toISOString();

  return {
    authNumber:    `PA-${requestId.slice(0, 8).toUpperCase()}`,
    status:        "approved",
    expiresAt,
    approvedCodes: params.procedureCodes,
    requestId,
    submittedAt,
    provider:      "mock",
  };
}

// ── Audit helper ──────────────────────────────────────────────────────────────

async function auditPriorAuthSubmission(
  params: PriorAuthParams,
  result: PriorAuthResult,
): Promise<void> {
  try {
    await storage.createAuditLog({
      userId:       `agent:prior-auth:${params.tenantId}`,
      userEmail:    null,
      action:       "create",
      resourceType: "prior_auth",
      resourceId:   result.requestId,
      patientId:    Number(params.patientId) || null,
      ipAddress:    null,
      userAgent:    "PriorAuthAgent/1.0",
      details: {
        provider:       result.provider,
        authNumber:     result.authNumber,
        status:         result.status,
        procedureCodes: params.procedureCodes,
        diagnosisCodes: params.diagnosisCodes,
        insurerId:      params.insurerId,
        tenantId:       params.tenantId,
      },
      phiAccessed: true,
    });
  } catch (err) {
    console.error("[PriorAuthAgent] audit log failed:", err);
  }
}

// ── Main exported function ────────────────────────────────────────────────────

/**
 * Submit a prior authorization request for one or more procedure codes.
 *
 * Uses Change Healthcare's Prior Auth API when CHANGE_HEALTHCARE_API_KEY is set;
 * otherwise falls back to mock mode (logs a warning).
 */
export async function submitPriorAuth(params: PriorAuthParams): Promise<PriorAuthResult> {
  const useMock = !CHANGE_HEALTHCARE_API_KEY;

  if (useMock) {
    console.warn(
      "[PriorAuthAgent] Running in MOCK mode — " +
      "set CHANGE_HEALTHCARE_API_KEY for live prior auth submission.",
    );
    const result = buildMockPriorAuth(params);
    await auditPriorAuthSubmission(params, result);
    return result;
  }

  const result = await submitCHCPriorAuth(params);
  await auditPriorAuthSubmission(params, result);
  return result;
}

/**
 * Server-side SOQL client. Read-only by contract — only supports SELECT.
 * Mirrors the production read-only posture from
 * `feedback_production_readonly_pull` memory.
 *
 * Tokens are read via ``readSFTokensWithFallback`` (DB-first, dev-file
 * fallback) per ENG-125. Refresh pushes the new payload back to the DB
 * resolver so the row stays current.
 */
import "server-only";
import { readSFTokensWithFallback, refreshAccessToken } from "./oauth";

const API_VERSION = "v60.0";

export interface SoqlResult<T> {
  totalSize: number;
  done: boolean;
  records: T[];
  nextRecordsUrl?: string;
}

export class SFNotConnectedError extends Error {
  constructor() {
    super("Salesforce not connected — run the OAuth flow first.");
    this.name = "SFNotConnectedError";
  }
}

export async function soql<T>(
  query: string,
  attempt = 0,
): Promise<SoqlResult<T>> {
  if (!query.trim().toLowerCase().startsWith("select")) {
    throw new Error("Only SELECT queries are allowed (read-only contract).");
  }
  const tokens = await readSFTokensWithFallback();
  if (!tokens) throw new SFNotConnectedError();

  const url = `${tokens.instance_url}/services/data/${API_VERSION}/query?q=${encodeURIComponent(query)}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
    cache: "no-store",
  });
  if (res.status === 401 && attempt === 0) {
    try {
      await refreshAccessToken();
    } catch {
      throw new SFNotConnectedError();
    }
    return soql<T>(query, attempt + 1);
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`SOQL request failed: ${res.status} ${text.slice(0, 200)}`);
  }
  return res.json();
}

/**
 * SOSL search — used for phone lookups where SOQL LIKE is unreliable
 * because SF stores phones in operator-entered formats (parens, dashes,
 * spaces). SOSL's `IN PHONE FIELDS` understands all of those.
 *
 * Read-only by contract: only `FIND` queries are accepted.
 */
export interface SoslSearchRecord {
  attributes: { type: string; url: string };
  Id: string;
  [key: string]: unknown;
}

export interface SoslResult {
  searchRecords: SoslSearchRecord[];
}

export async function sosl(
  query: string,
  attempt = 0,
): Promise<SoslResult> {
  if (!query.trim().toLowerCase().startsWith("find")) {
    throw new Error("Only FIND queries are allowed (read-only contract).");
  }
  const tokens = await readSFTokensWithFallback();
  if (!tokens) throw new SFNotConnectedError();

  const url = `${tokens.instance_url}/services/data/${API_VERSION}/search/?q=${encodeURIComponent(query)}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
    cache: "no-store",
  });
  if (res.status === 401 && attempt === 0) {
    try {
      await refreshAccessToken();
    } catch {
      throw new SFNotConnectedError();
    }
    return sosl(query, attempt + 1);
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`SOSL request failed: ${res.status} ${text.slice(0, 200)}`);
  }
  return res.json();
}

/**
 * Server-side CareStack API client. Read-only by contract.
 * Auto-refreshes the access_token by re-running the password grant
 * when the cached token has expired or the API returns 401.
 *
 * Vendor / account / API base config is resolved DB-first via the
 * FastAPI internal credential resolver (ENG-125), env-fallback on
 * any failure. Token caching stays in the dev token file because the
 * IdP issues short-lived tokens and the file write is the local
 * fast-path.
 */
import "server-only";
import { fetchAccessToken, loadCsConfig } from "./auth";
import { readCSTokens } from "./tokens";

export class CSNotConnectedError extends Error {
  constructor() {
    super("CareStack not connected — call /api/integrations/carestack/connect/start first.");
    this.name = "CSNotConnectedError";
  }
}

async function getValidToken(): Promise<{ token: string; accountId: string }> {
  const cached = await readCSTokens();
  if (cached) {
    const expires = new Date(cached.expires_at).getTime();
    if (expires > Date.now() + 30_000) {
      return { token: cached.access_token, accountId: cached.account_id };
    }
  }
  const fresh = await fetchAccessToken();
  return { token: fresh.access_token, accountId: fresh.account_id };
}

export async function csGet<T>(
  path: string,
  query?: Record<string, string | number>,
  attempt = 0,
): Promise<T> {
  // Path must NOT start with `/` — we always join with the base URL.
  const trimmed = path.startsWith("/") ? path.slice(1) : path;
  const cfg = await loadCsConfig();
  const base = cfg.api_base_url.replace(/\/$/, "");
  const search = query
    ? "?" + new URLSearchParams(
        Object.entries(query).map(([k, v]) => [k, String(v)]),
      ).toString()
    : "";
  const url = `${base}/${trimmed}${search}`;

  const { token, accountId } = await getValidToken();
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      VendorKey: cfg.vendor_key,
      AccountKey: cfg.account_key,
      AccountId: accountId,
      Accept: "application/json",
    },
    cache: "no-store",
  });

  if (res.status === 401 && attempt === 0) {
    // Token may have been invalidated server-side — force a fresh grant.
    await fetchAccessToken();
    return csGet<T>(path, query, attempt + 1);
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(
      `CareStack ${trimmed} failed: ${res.status} ${text.slice(0, 200)}`,
    );
  }
  return res.json();
}

export async function csPost<T>(
  path: string,
  body: Record<string, unknown>,
  attempt = 0,
): Promise<T> {
  const trimmed = path.startsWith("/") ? path.slice(1) : path;
  const cfg = await loadCsConfig();
  const base = cfg.api_base_url.replace(/\/$/, "");
  const url = `${base}/${trimmed}`;

  const { token, accountId } = await getValidToken();
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      VendorKey: cfg.vendor_key,
      AccountKey: cfg.account_key,
      AccountId: accountId,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  if (res.status === 401 && attempt === 0) {
    await fetchAccessToken();
    return csPost<T>(path, body, attempt + 1);
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(
      `CareStack POST ${trimmed} failed: ${res.status} ${text.slice(0, 200)}`,
    );
  }
  return res.json();
}

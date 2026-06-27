/**
 * Server-side credential resolver — DB-first, env-fallback.
 *
 * Bridges the Next.js server-side route handlers to the FastAPI
 * ``/_internal/credentials/...`` endpoint. All ENG-125 SF / CareStack
 * code paths route through here:
 *
 *   1. Try FastAPI (DB-backed, decrypted by IntegrationCredentialService).
 *   2. On any failure (404, network error, 503 not_configured) the
 *      caller falls back to its existing ``process.env.*`` lookup.
 *
 * NEVER import from a client component. The internal token is a
 * server-only secret (``INTERNAL_CREDENTIAL_TOKEN``) and must not
 * land in the browser bundle.
 */
import "server-only";

const DEFAULT_API_BASE = "http://localhost:8000";
const METADATA_IDENTITY_URL =
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity";

function apiBase(): string {
  const raw =
    process.env.INTERNAL_API_URL ??
    process.env.INTERNAL_API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    DEFAULT_API_BASE;
  return raw.replace(/\/$/, "");
}

function internalToken(): string | undefined {
  const t = process.env.INTERNAL_CREDENTIAL_TOKEN;
  return t && t.length > 0 ? t : undefined;
}

function shouldAttachCloudRunIdentity(apiBaseUrl: string): boolean {
  if (!process.env.K_SERVICE) return false;
  try {
    return new URL(apiBaseUrl).hostname.endsWith(".run.app");
  } catch {
    return false;
  }
}

async function cloudRunIdentityToken(
  apiBaseUrl: string,
): Promise<string | undefined> {
  if (!shouldAttachCloudRunIdentity(apiBaseUrl)) return undefined;
  const audience = apiBaseUrl.replace(/\/$/, "");
  const url =
    `${METADATA_IDENTITY_URL}?` +
    new URLSearchParams({ audience, format: "full" }).toString();
  try {
    const res = await fetch(url, {
      headers: { "Metadata-Flavor": "Google" },
      cache: "no-store",
    });
    if (!res.ok) return undefined;
    const token = (await res.text()).trim();
    return token.length > 0 ? token : undefined;
  } catch {
    return undefined;
  }
}

async function internalHeaders(
  apiBaseUrl: string,
  token: string,
): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    "X-Internal-Token": token,
    Accept: "application/json",
  };
  const identityToken = await cloudRunIdentityToken(apiBaseUrl);
  if (identityToken) headers.Authorization = `Bearer ${identityToken}`;
  return headers;
}

/** Per-process in-memory cache (TTL = 60s) so repeated reads inside a
 *  single request batch do not hammer the API. The TTL is short enough
 *  that a refresh cycle picks up a rotation within a minute.
 *
 *  We cache by ``provider:kind`` — multi-mailbox is keyed inside the
 *  payload (``mailbox_email``) so callers that need a specific mailbox
 *  must pass it as part of the cache key (future ext.). */
type CacheEntry = { value: Record<string, unknown>; expires: number };
const _cache = new Map<string, CacheEntry>();
const TTL_MS = 60 * 1000;

function cacheKey(provider: string, kind: string): string {
  return `${provider}:${kind}`;
}

/** Public surface — returns the decrypted credential payload from the
 *  DB resolver, or ``null`` when the resolver is unreachable / 404 /
 *  not-configured. The caller falls back to env on null.
 *
 *  Errors (4xx other than 404, network errors) are converted to ``null``
 *  by design: this resolver is best-effort and the env-fallback covers
 *  the gap. The Next.js handler still owns logging — we don't log here
 *  to avoid noise on every page load. */
export async function resolveCredential(
  provider: string,
  kind: string,
): Promise<Record<string, unknown> | null> {
  const token = internalToken();
  if (!token) return null;

  const key = cacheKey(provider, kind);
  const cached = _cache.get(key);
  if (cached && cached.expires > Date.now()) {
    return cached.value;
  }

  const base = apiBase();
  const url = `${base}/_internal/credentials/${encodeURIComponent(provider)}/${encodeURIComponent(kind)}`;
  let res: Response;
  try {
    res = await fetch(url, {
      headers: await internalHeaders(base, token),
      cache: "no-store",
    });
  } catch {
    // Network error — fall back to env.
    return null;
  }
  if (!res.ok) {
    // 404 (no row), 503 (not configured), 401 (token wrong) — all
    // become null. The caller falls back to env.
    return null;
  }
  const json = (await res.json()) as Record<string, unknown>;
  _cache.set(key, { value: json, expires: Date.now() + TTL_MS });
  return json;
}

/** PUT a fresh payload to the DB resolver. Used by the SF refresh flow
 *  (``oauth.ts``) when a new ``access_token`` is issued. Returns true on
 *  success, false on any failure — the refresh-token caller should also
 *  write to the local dev token file as a Phase-1 fallback so dev keeps
 *  working when the resolver is offline.
 */
export async function persistCredential(
  provider: string,
  kind: string,
  payload: Record<string, unknown>,
): Promise<boolean> {
  const token = internalToken();
  if (!token) return false;
  const base = apiBase();
  const url = `${base}/_internal/credentials/${encodeURIComponent(provider)}/${encodeURIComponent(kind)}`;
  try {
    const res = await fetch(url, {
      method: "PUT",
      headers: {
        ...(await internalHeaders(base, token)),
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    if (res.ok) {
      // Bust the cache so the next read sees the fresh payload.
      _cache.delete(cacheKey(provider, kind));
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

/** Test seam: clear the in-memory cache. Production code never calls
 *  this; vitest does between cases. */
export function _resetCredentialCacheForTests(): void {
  _cache.clear();
}

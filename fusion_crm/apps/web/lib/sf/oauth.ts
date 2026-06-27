/**
 * Server-side only. Salesforce OAuth Web Server Flow with PKCE.
 *
 * The Connected App we share with `dental-calc-mvp` requires PKCE
 * (`code_challenge` + `code_verifier` with S256). Without it, SF rejects
 * the auth request with the misleading `invalid_client_id` error.
 *
 * Credential resolution (ENG-125): SF client config (`client_id`,
 * `client_secret`, `callback_url`, `domain`) is read DB-first via the
 * FastAPI ``/_internal/credentials/salesforce/api_key`` resolver, with
 * env-fallback on any failure. The DB-resolved row is the source of
 * truth in production; ``.env`` keys are bootstrap-only.
 *
 * Refresh-token writes also PUT the new payload back to the resolver
 * so the DB row stays in sync with the Phase-1 dev token file.
 */
import "server-only";
import crypto from "node:crypto";
import { persistCredential, resolveCredential } from "@/lib/credentials/resolver";
import { readTokens, writeTokens, type SFTokens } from "./tokens";

interface SFApiKeyPayload {
  client_id?: unknown;
  client_secret?: unknown;
  callback_url?: unknown;
  domain?: unknown;
}

interface SFOAuthTokenPayload {
  access_token?: unknown;
  refresh_token?: unknown;
  instance_url?: unknown;
  issued_at?: unknown;
}

interface SFClientConfig {
  client_id: string;
  client_secret: string;
  callback_url: string;
  domain: string;
}

function env(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing env var: ${name}`);
  return v;
}

function envOptional(name: string): string | undefined {
  const v = process.env[name];
  return v && v.length > 0 ? v : undefined;
}

function asString(v: unknown): string | undefined {
  return typeof v === "string" && v.length > 0 ? v : undefined;
}

/** Resolve SF client config DB-first, env-fallback. Throws only when
 *  neither source provides ``client_id`` + ``client_secret`` — those
 *  are the irreducible minimum. */
async function loadClientConfig(): Promise<SFClientConfig> {
  const dbPayload = (await resolveCredential(
    "salesforce",
    "api_key",
  )) as SFApiKeyPayload | null;

  const clientId =
    asString(dbPayload?.client_id) ?? envOptional("SALESFORCE_CLIENT_ID");
  const clientSecret =
    asString(dbPayload?.client_secret) ??
    envOptional("SALESFORCE_CLIENT_SECRET");
  const callbackUrl =
    asString(dbPayload?.callback_url) ??
    envOptional("SALESFORCE_CALLBACK_URL");
  const domainValue =
    asString(dbPayload?.domain) ??
    envOptional("SALESFORCE_DOMAIN") ??
    "login.salesforce.com";

  if (!clientId || !clientSecret) {
    throw new Error(
      "Salesforce client config missing — set SALESFORCE_CLIENT_ID + SALESFORCE_CLIENT_SECRET (or seed tenant.integration_credential)",
    );
  }
  if (!callbackUrl) {
    throw new Error(
      "Salesforce callback URL missing — set SALESFORCE_CALLBACK_URL or seed callback_url in DB",
    );
  }
  return {
    client_id: clientId,
    client_secret: clientSecret,
    callback_url: callbackUrl,
    domain: domainValue,
  };
}

function base64url(buf: Buffer): string {
  return buf
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

export function generatePkcePair(): { verifier: string; challenge: string } {
  const verifier = base64url(crypto.randomBytes(32));
  const challenge = base64url(crypto.createHash("sha256").update(verifier).digest());
  return { verifier, challenge };
}

export async function buildAuthUrl(
  challenge: string,
  state?: string,
): Promise<string> {
  const cfg = await loadClientConfig();
  const params = new URLSearchParams({
    client_id: cfg.client_id,
    redirect_uri: cfg.callback_url,
    response_type: "code",
    scope: "api refresh_token offline_access",
    code_challenge: challenge,
    code_challenge_method: "S256",
    ...(state ? { state } : {}),
  });
  return `https://${cfg.domain}/services/oauth2/authorize?${params.toString()}`;
}

interface SFTokenResponse {
  access_token: string;
  refresh_token?: string;
  instance_url: string;
  issued_at?: string;
  token_type: string;
  signature?: string;
}

/** Persist a refreshed-or-issued SF token into both stores:
 *  - FastAPI resolver (DB-backed source of truth for production);
 *  - dev token file (local fallback so sessions survive Next.js restarts).
 *
 *  Cloud Run runs the app from a read-only image path, so the dev-file
 *  write is best-effort. Local dev still works when the resolver is offline
 *  because the file write can succeed independently.
 */
async function persistTokens(tokens: {
  access_token: string;
  refresh_token?: string;
  instance_url: string;
  issued_at?: string;
}): Promise<SFTokens> {
  const saved: SFTokens = {
    ...tokens,
    saved_at: new Date().toISOString(),
  };

  const dbPersisted = await persistCredential("salesforce", "oauth_token", {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
    instance_url: tokens.instance_url,
    issued_at: tokens.issued_at,
  });

  let filePersisted = false;
  try {
    await writeTokens(tokens);
    filePersisted = true;
  } catch {
    // Production Cloud Run cannot write to /app; DB persistence above is
    // the production source of truth. Keep this path quiet to avoid
    // logging token-refresh noise on every expired access token.
  }

  if (!dbPersisted && !filePersisted) {
    throw new Error("Failed to persist Salesforce tokens");
  }
  return saved;
}

export async function exchangeCode(
  code: string,
  codeVerifier: string,
): Promise<SFTokens> {
  const cfg = await loadClientConfig();
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    client_id: cfg.client_id,
    client_secret: cfg.client_secret,
    redirect_uri: cfg.callback_url,
    code_verifier: codeVerifier,
  });
  const res = await fetch(`https://${cfg.domain}/services/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`SF token exchange failed: ${res.status} ${text}`);
  }
  const data = (await res.json()) as SFTokenResponse;
  return persistTokens({
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    instance_url: data.instance_url,
    issued_at: data.issued_at,
  });
}

/** Read the canonical SF tokens (DB-first when available, dev-file
 *  otherwise). Used by the SOQL/SOSL client to grab a current
 *  ``access_token`` + ``instance_url``. */
export async function readSFTokensWithFallback(): Promise<SFTokens | null> {
  // Try resolver first.
  const dbPayload = (await resolveCredential(
    "salesforce",
    "oauth_token",
  )) as SFOAuthTokenPayload | null;
  if (dbPayload) {
    const accessToken = asString(dbPayload.access_token);
    const instanceUrl = asString(dbPayload.instance_url);
    if (accessToken && instanceUrl) {
      return {
        access_token: accessToken,
        refresh_token: asString(dbPayload.refresh_token),
        instance_url: instanceUrl,
        issued_at: asString(dbPayload.issued_at),
        // ``saved_at`` is required by SFTokens; use issued_at when present.
        saved_at:
          asString(dbPayload.issued_at) ?? new Date().toISOString(),
      };
    }
  }
  // Fall back to the local dev file.
  return readTokens();
}

export async function refreshAccessToken(): Promise<SFTokens> {
  const cfg = await loadClientConfig();
  const current = await readSFTokensWithFallback();
  if (!current?.refresh_token) {
    throw new Error("No SF refresh_token available — reconnect");
  }
  const body = new URLSearchParams({
    grant_type: "refresh_token",
    refresh_token: current.refresh_token,
    client_id: cfg.client_id,
    client_secret: cfg.client_secret,
  });
  const res = await fetch(`https://${cfg.domain}/services/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`SF refresh failed: ${res.status} ${text}`);
  }
  const data = (await res.json()) as SFTokenResponse;
  return persistTokens({
    access_token: data.access_token,
    refresh_token: data.refresh_token ?? current.refresh_token,
    instance_url: data.instance_url ?? current.instance_url,
    issued_at: data.issued_at ?? current.issued_at,
  });
}

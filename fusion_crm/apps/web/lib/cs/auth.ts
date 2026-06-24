/**
 * Server-side CareStack OAuth Password Grant.
 *
 * Empirically verified by probing the IdP:
 *   username = CARESTACK_VENDOR_KEY
 *   password = CARESTACK_ACCOUNT_KEY
 *   scope    = "" (empty)
 *
 * Credential resolution (ENG-125): config (`client_id`, `client_secret`,
 * `vendor_key`, `account_key`, `account_id`, IdP base URL) is read
 * DB-first via the FastAPI resolver, env-fallback on any failure. The
 * short-lived access token is cached to a dev file when possible; production
 * Cloud Run can run without that cache because the password grant is
 * repeatable.
 */
import "server-only";
import { resolveCredential } from "@/lib/credentials/resolver";
import { type CSTokens, writeCSTokens } from "./tokens";

interface CSPasswordGrantPayload {
  client_id?: unknown;
  client_secret?: unknown;
  vendor_key?: unknown;
  account_key?: unknown;
  account_id?: unknown;
  idp_base_url?: unknown;
  api_base_url?: unknown;
  api_version?: unknown;
}

export interface CSResolvedConfig {
  client_id: string;
  client_secret: string;
  vendor_key: string;
  account_key: string;
  account_id: string;
  idp_base_url: string;
  api_base_url: string;
  api_version: string;
}

function asString(v: unknown): string | undefined {
  return typeof v === "string" && v.length > 0 ? v : undefined;
}

function envOptional(name: string): string | undefined {
  const v = process.env[name];
  return v && v.length > 0 ? v : undefined;
}

/** Resolve CareStack config DB-first, env-fallback. Throws when any
 *  required field is missing from BOTH sources. */
export async function loadCsConfig(): Promise<CSResolvedConfig> {
  const dbPayload = (await resolveCredential(
    "carestack",
    "password_grant",
  )) as CSPasswordGrantPayload | null;

  const clientId =
    asString(dbPayload?.client_id) ?? envOptional("CARESTACK_CLIENT_ID");
  const clientSecret =
    asString(dbPayload?.client_secret) ??
    envOptional("CARESTACK_CLIENT_SECRET");
  const vendorKey =
    asString(dbPayload?.vendor_key) ?? envOptional("CARESTACK_VENDOR_KEY");
  const accountKey =
    asString(dbPayload?.account_key) ?? envOptional("CARESTACK_ACCOUNT_KEY");
  const accountId =
    asString(dbPayload?.account_id) ?? envOptional("CARESTACK_ACCOUNT_ID");
  const idpBase =
    asString(dbPayload?.idp_base_url) ??
    envOptional("CARESTACK_IDP_BASE_URL");
  const apiBase =
    asString(dbPayload?.api_base_url) ??
    envOptional("CARESTACK_API_BASE_URL");
  const apiVersion =
    asString(dbPayload?.api_version) ??
    envOptional("CARESTACK_API_VERSION") ??
    "v1.0";

  const missing = (
    [
      ["CARESTACK_CLIENT_ID", clientId],
      ["CARESTACK_CLIENT_SECRET", clientSecret],
      ["CARESTACK_VENDOR_KEY", vendorKey],
      ["CARESTACK_ACCOUNT_KEY", accountKey],
      ["CARESTACK_ACCOUNT_ID", accountId],
      ["CARESTACK_IDP_BASE_URL", idpBase],
      ["CARESTACK_API_BASE_URL", apiBase],
    ] as const
  )
    .filter(([, v]) => !v)
    .map(([n]) => n);
  if (missing.length > 0) {
    throw new Error(
      `CareStack config missing — set ${missing.join(", ")} (or seed tenant.integration_credential)`,
    );
  }
  return {
    client_id: clientId as string,
    client_secret: clientSecret as string,
    vendor_key: vendorKey as string,
    account_key: accountKey as string,
    account_id: accountId as string,
    idp_base_url: idpBase as string,
    api_base_url: apiBase as string,
    api_version: apiVersion,
  };
}

interface CSTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export async function fetchAccessToken(): Promise<CSTokens> {
  const cfg = await loadCsConfig();
  const url = `${cfg.idp_base_url}/connect/token`;
  const body = new URLSearchParams({
    grant_type: "password",
    client_id: cfg.client_id,
    client_secret: cfg.client_secret,
    username: cfg.vendor_key,
    password: cfg.account_key,
    scope: "",
  });
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`CareStack token request failed: ${res.status} ${text}`);
  }
  const data = (await res.json()) as CSTokenResponse;
  const expiresAt = new Date(Date.now() + data.expires_in * 1000).toISOString();
  const token: CSTokens = {
    access_token: data.access_token,
    token_type: data.token_type,
    expires_at: expiresAt,
    account_id: cfg.account_id,
    saved_at: new Date().toISOString(),
    last_sync: null,
  };
  try {
    await writeCSTokens({
      access_token: token.access_token,
      token_type: token.token_type,
      expires_at: token.expires_at,
      account_id: token.account_id,
      last_sync: token.last_sync,
    });
  } catch {
    // Cloud Run's /app path is read-only. The token is still valid for the
    // current request; future requests can repeat the password grant.
  }
  return token;
}

import { createHash, timingSafeEqual } from "node:crypto";
import type { Request, Response, NextFunction } from "express";
import { storage } from "../storage";
import { type Capability, type Principal, makePrincipal } from "../tools/types";

// MCP clients are services (Claude Code, Codex, internal AI agents) — they
// can't go through OIDC like staff do. Two auth modes are supported:
//
//   1. Per-key DB auth (preferred): the bearer token is hashed (SHA-256)
//      and looked up in `mcp_api_keys`. Each row carries its own
//      capability list, so a marketing-AI key can be issued without PHI
//      access while a clinical-AI key gets phi.read. Revocable, auditable,
//      individually rotatable.
//
//   2. Shared env-key fallback (legacy): if `MCP_API_KEY` is set, that
//      single key grants the full capability set. Useful for dev/staging
//      before the keys table is provisioned; should not be used in prod.
//      If both modes are configured, the DB lookup wins.

declare module "express" {
  interface Request {
    mcpPrincipal?: Principal;
    mcpKeyId?: number; // DB-mode only; absent for env fallback
  }
}

function sha256Hex(input: string): string {
  return createHash("sha256").update(input).digest("hex");
}

// Constant-time compare to avoid leaking key prefix via response timing.
// Both inputs are hex hashes of equal length, so direct byte compare works.
function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  const aBuf = Buffer.from(a);
  const bBuf = Buffer.from(b);
  return timingSafeEqual(aBuf, bBuf);
}

function parseBearer(req: Request): string | null {
  const header = req.header("authorization") ?? "";
  const match = /^Bearer\s+(.+)$/i.exec(header);
  return match ? match[1] : null;
}

function unauthorized(res: Response, message = "Unauthorized") {
  return res.status(401).json({
    error: { code: -32001, message },
  });
}

export async function mcpAuth(req: Request, res: Response, next: NextFunction) {
  const envKey = process.env.MCP_API_KEY;
  const token = parseBearer(req);

  if (!token) {
    return unauthorized(res);
  }

  // Try DB-mode first. We hash the presented token and look up by hash so
  // the DB never stores plaintext.
  const presentedHash = sha256Hex(token);

  let row;
  try {
    row = await storage.getMcpApiKeyByHash(presentedHash);
  } catch (err) {
    console.error("MCP auth: keys table lookup failed:", err);
    row = undefined;
  }

  if (row) {
    if (!row.enabled) {
      return unauthorized(res, "API key has been revoked");
    }
    // Fire-and-forget the lastUsedAt bump — we don't want to slow the
    // request waiting for it, but we DO want it to land.
    void storage.touchMcpApiKeyLastUsed(row.id).catch((err) => {
      console.error("MCP auth: lastUsedAt bump failed:", err);
    });

    req.mcpPrincipal = makePrincipal({
      userId: `mcp:${row.id}`,
      email: row.label,
      // Key's tenant binding wins. Falls back to DEFAULT_TENANT_ID if the
      // key row predates the tenant column (during the rolling backfill).
      tenantId: (row as any).tenantId ?? process.env.DEFAULT_TENANT_ID,
      capabilities: (row.capabilities ?? []) as Capability[],
    });
    req.mcpKeyId = row.id;
    return next();
  }

  // Env fallback. Constant-time compare against the hashed env value so
  // we behave identically to the DB path's timing.
  if (envKey && safeEqual(presentedHash, sha256Hex(envKey))) {
    req.mcpPrincipal = makePrincipal({
      userId: "mcp:env",
      email: "mcp-env-fallback",
      // Env fallback grants the full capability set — same posture as
      // pre-DB-mode. Production should switch off the env fallback by
      // unsetting MCP_API_KEY once real keys are provisioned.
      capabilities: ["phi.read", "phi.write"],
    });
    return next();
  }

  // No DB row, no env match. If neither is configured at all, give a
  // clearer error so operators can see the deploy is misconfigured.
  if (!envKey) {
    return unauthorized(
      res,
      "MCP not configured (provision an mcp_api_keys row or set MCP_API_KEY)",
    );
  }

  return unauthorized(res);
}

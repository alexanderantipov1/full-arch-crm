import { randomBytes, createHash } from "node:crypto";
import { storage } from "../storage";
import type { Capability } from "../tools/types";

// Helpers for provisioning and managing MCP API keys. Used by the admin
// HTTP endpoints and by the CLI script (`scripts/create-mcp-key.ts`).
//
// Plaintext rule: the token returned by `generateMcpApiKey` is the ONLY
// time the operator can see the bearer value. The DB stores only the
// SHA-256 hash. If a key is lost, revoke and reissue.

const TOKEN_BYTES = 32; // 256 bits → 64 hex chars
const TOKEN_PREFIX = "mcp_";

export function sha256Hex(input: string): string {
  return createHash("sha256").update(input).digest("hex");
}

export interface NewMcpApiKey {
  id: number;
  label: string;
  // Plaintext token. Surface to the operator exactly once, then forget.
  token: string;
  capabilities: Capability[];
}

export async function generateMcpApiKey(opts: {
  label: string;
  capabilities: Capability[];
  createdBy?: string;
}): Promise<NewMcpApiKey> {
  if (!opts.label || opts.label.trim().length === 0) {
    throw new Error("label is required");
  }
  // Random token. Prefixed so it's obvious in logs / accidental commits
  // what kind of secret it is (helps GitHub's secret scanning, too).
  const raw = randomBytes(TOKEN_BYTES).toString("hex");
  const token = `${TOKEN_PREFIX}${raw}`;
  const keyHash = sha256Hex(token);

  const row = await storage.createMcpApiKey({
    label: opts.label.trim(),
    keyHash,
    capabilities: opts.capabilities,
    enabled: true,
    createdBy: opts.createdBy ?? null,
  } as any);

  return {
    id: row.id,
    label: row.label,
    token,
    capabilities: opts.capabilities,
  };
}

// Strip the `keyHash` from a row before sending it over the wire. The hash
// alone doesn't reveal the token, but there's no operator use for it and
// less surface area is better.
export function sanitizeMcpApiKey(row: Awaited<ReturnType<typeof storage.listMcpApiKeys>>[number]) {
  const { keyHash, ...rest } = row;
  return rest;
}

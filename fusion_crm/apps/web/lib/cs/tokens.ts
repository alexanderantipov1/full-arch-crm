/**
 * Server-side only. CareStack token storage.
 *
 * CareStack does NOT issue a refresh_token (per the .env comment) — we
 * re-run the password grant when the access_token expires (~2h TTL).
 */
import "server-only";
import fs from "node:fs/promises";
import path from "node:path";
import { z } from "zod";

const TOKENS_FILE = path.resolve(process.cwd(), ".cs-tokens.json");

// Datetime fields tolerate both `Z` (Next.js `Date.toISOString()`) and
// `+00:00` (Python `datetime.isoformat()`) — see
// `apps/web/lib/api/schemas/common.ts` and the SF token parser for the
// same trap.
const LastSyncSchema = z
  .object({
    id: z.string(),
    status: z.enum(["running", "success", "failed"]),
    records_pulled: z.number().int().nonnegative(),
    finished_at: z.string().datetime({ offset: true }).nullable(),
  })
  .nullable();

const CSTokensSchema = z.object({
  access_token: z.string().min(1),
  token_type: z.string(),
  expires_at: z.string().datetime({ offset: true }),
  account_id: z.string(),
  saved_at: z.string().datetime({ offset: true }),
  last_sync: LastSyncSchema.optional().default(null),
});
export type CSTokens = z.infer<typeof CSTokensSchema>;
export type CSLastSync = z.infer<typeof LastSyncSchema>;

export async function readCSTokens(): Promise<CSTokens | null> {
  try {
    const raw = await fs.readFile(TOKENS_FILE, "utf8");
    return CSTokensSchema.parse(JSON.parse(raw));
  } catch {
    return null;
  }
}

export async function writeCSTokens(
  tokens: Omit<CSTokens, "saved_at">,
): Promise<void> {
  const payload: CSTokens = {
    ...tokens,
    saved_at: new Date().toISOString(),
  };
  await fs.writeFile(TOKENS_FILE, JSON.stringify(payload, null, 2), "utf8");
}

export async function clearCSTokens(): Promise<void> {
  try {
    await fs.unlink(TOKENS_FILE);
  } catch {
    // already gone — fine
  }
}

export async function recordCSLastSync(sync: CSLastSync): Promise<void> {
  const current = await readCSTokens();
  if (!current) return;
  await fs.writeFile(
    TOKENS_FILE,
    JSON.stringify({ ...current, last_sync: sync }, null, 2),
    "utf8",
  );
}

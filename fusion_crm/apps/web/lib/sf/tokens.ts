/**
 * Server-side only. NEVER import from client components.
 *
 * Token storage for the dev-mode Salesforce OAuth flow. We persist tokens
 * to a file at the apps/web/.sf-tokens.json path so dev sessions survive
 * Next.js restarts. The file is gitignored. In production, this whole
 * surface is replaced by `packages.integrations` + encrypted token columns
 * (FUS-22) — see apps/web/CLAUDE.md.
 */
import "server-only";
import fs from "node:fs/promises";
import path from "node:path";
import { z } from "zod";

const TOKENS_FILE = path.resolve(process.cwd(), ".sf-tokens.json");

// `saved_at` may be written by either the Next.js OAuth flow
// (`new Date().toISOString()` → `Z` suffix) or the Python token-refresh
// path (`datetime.now(UTC).isoformat()` → `+00:00` suffix). Strict
// `z.string().datetime()` rejects the offset form and crashes readTokens
// with `SFNotConnectedError` even when the file is healthy — see
// `feedback_prod_deploy_traps.md` trap #1 / ENG-145.
const SFTokensSchema = z.object({
  access_token: z.string().min(1),
  refresh_token: z.string().min(1).optional(),
  instance_url: z.string().url(),
  issued_at: z.string().optional(),
  saved_at: z.string().datetime({ offset: true }),
});
export type SFTokens = z.infer<typeof SFTokensSchema>;

export async function readTokens(): Promise<SFTokens | null> {
  try {
    const raw = await fs.readFile(TOKENS_FILE, "utf8");
    return SFTokensSchema.parse(JSON.parse(raw));
  } catch {
    return null;
  }
}

export async function writeTokens(
  tokens: Omit<SFTokens, "saved_at">,
): Promise<void> {
  const payload: SFTokens = {
    ...tokens,
    saved_at: new Date().toISOString(),
  };
  await fs.writeFile(TOKENS_FILE, JSON.stringify(payload, null, 2), "utf8");
}

export async function clearTokens(): Promise<void> {
  try {
    await fs.unlink(TOKENS_FILE);
  } catch {
    // already gone — fine
  }
}

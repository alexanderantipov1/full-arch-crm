// Backfill script — creates a "default" tenant and assigns every existing
// row in tenant-scoped tables to it.
//
// Run order:
//   1. Apply schema first (npm run db:push) so `tenants` table and the
//      `tenant_id` columns exist on patients/leads/persons/mcp_api_keys.
//   2. Run this script ONCE per environment:
//        tsx scripts/backfill-tenants.ts
//      Idempotent — re-running creates no duplicates; rows that already
//      have tenantId are skipped.
//   3. After this runs, set DEFAULT_TENANT_ID in the env to the printed
//      UUID so principalFromReq and mcpAuth bind new sessions/keys to
//      that tenant.
//
// Single-tenant deployment: that's it; one default tenant + everything
// in it. Multi-tenant deployment: this gives you a starting point;
// provision additional tenants via the (future) admin UI and migrate
// rows out of "default" as clinics onboard.

import { db } from "../server/db";
import { tenants, patients, leads, persons, mcpApiKeys } from "@shared/schema";
import { eq, isNull } from "drizzle-orm";

const DEFAULT_TENANT_SLUG = "default";
const DEFAULT_TENANT_NAME = "Default Clinic";

async function ensureDefaultTenant(): Promise<string> {
  const [existing] = await db.select().from(tenants).where(eq(tenants.slug, DEFAULT_TENANT_SLUG)).limit(1);
  if (existing) return existing.id;
  const [created] = await db
    .insert(tenants)
    .values({ slug: DEFAULT_TENANT_SLUG, name: DEFAULT_TENANT_NAME, settings: null, enabled: true })
    .returning();
  return created.id;
}

async function backfillTable(name: string, table: any, tenantId: string): Promise<number> {
  const result = await db
    .update(table)
    .set({ tenantId })
    .where(isNull(table.tenantId))
    .returning({ id: table.id });
  console.log(`[backfill-tenants] ${name}: assigned ${result.length} row(s)`);
  return result.length;
}

async function main(): Promise<void> {
  console.log("[backfill-tenants] starting…");

  const defaultTenantId = await ensureDefaultTenant();
  console.log(`[backfill-tenants] default tenant uuid: ${defaultTenantId}`);

  await backfillTable("persons", persons, defaultTenantId);
  await backfillTable("patients", patients, defaultTenantId);
  await backfillTable("leads", leads, defaultTenantId);
  await backfillTable("mcp_api_keys", mcpApiKeys, defaultTenantId);

  console.log("\n[backfill-tenants] done.");
  console.log(`\nSet this in your environment so new sessions bind correctly:`);
  console.log(`  DEFAULT_TENANT_ID=${defaultTenantId}\n`);
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("[backfill-tenants] FAILED:", err);
    process.exit(1);
  });

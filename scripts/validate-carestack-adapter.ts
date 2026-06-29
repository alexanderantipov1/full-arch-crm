#!/usr/bin/env ts-node
/**
 * validate-carestack-adapter.ts
 * ─────────────────────────────
 * Validation script that confirms the CareStackDirectAdapter can successfully
 * connect to the CareStack REST API and pull real patient data.
 *
 * Run with:
 *   npx ts-node scripts/validate-carestack-adapter.ts
 *
 * Required env vars (copy from .env.example → .env and fill in):
 *   CARESTACK_IDP_BASE_URL, CARESTACK_API_BASE_URL,
 *   CARESTACK_CLIENT_ID, CARESTACK_CLIENT_SECRET,
 *   CARESTACK_VENDOR_KEY, CARESTACK_ACCOUNT_KEY, CARESTACK_ACCOUNT_ID
 *
 * Exit codes:
 *   0 — all checks passed (adapter is production-ready)
 *   1 — one or more checks failed (review output for details)
 *
 * HIPAA note: This script never prints PHI to stdout. Patient names,
 * DOBs, SSNs, and contact info are masked in all log output.
 */

import "dotenv/config"; // loads .env automatically
import { CareStackDirectAdapter, careStackConfigFromEnv } from "../server/adapters/implementations/carestack-direct-adapter";
import type { CanonicalPatient, CanonicalTreatmentPlan, CanonicalMedicalHistory } from "../server/adapters/types";

// ─── HIPAA-safe masking ───────────────────────────────────────────────────────

function maskName(name: string | undefined): string {
  if (!name) return "(none)";
  const parts = name.trim().split(/\s+/);
  return parts.map(p => p[0] + "*".repeat(Math.max(0, p.length - 1))).join(" ");
}

function maskId(id: string | undefined): string {
  if (!id) return "(none)";
  return id.length <= 6 ? "***" : id.slice(0, 3) + "..." + id.slice(-3);
}

// ─── Result tracking ──────────────────────────────────────────────────────────

interface CheckResult {
  name: string;
  passed: boolean;
  detail: string;
  durationMs: number;
}

const results: CheckResult[] = [];

async function check(
  name: string,
  fn: () => Promise<string>
): Promise<string | null> {
  const start = Date.now();
  try {
    const detail = await fn();
    const durationMs = Date.now() - start;
    results.push({ name, passed: true, detail, durationMs });
    console.log(`  ✅  ${name} (${durationMs}ms)`);
    console.log(`       ${detail}`);
    return detail;
  } catch (err: unknown) {
    const durationMs = Date.now() - start;
    const msg = err instanceof Error ? err.message : String(err);
    results.push({ name, passed: false, detail: msg, durationMs });
    console.error(`  ❌  ${name} (${durationMs}ms)`);
    console.error(`       ${msg}`);
    return null;
  }
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  console.log("\n═══════════════════════════════════════════════════════════════");
  console.log("  CareStack Direct Adapter — Validation Suite");
  console.log("  full-arch-crm → CareStack REST API connectivity check");
  console.log(`  Run at: ${new Date().toISOString()}`);
  console.log("═══════════════════════════════════════════════════════════════\n");

  // ── 1. Load config from env ────────────────────────────────────────────────
  console.log("[ 1 ] Loading adapter config from environment...");
  let config: ReturnType<typeof careStackConfigFromEnv>;
  try {
    config = careStackConfigFromEnv();
    console.log(`  ✅  Config loaded`);
    console.log(`       IDP:  ${config.idpBaseUrl}`);
    console.log(`       API:  ${config.apiBaseUrl}`);
    console.log(`       Account: ${maskId(String(config.accountId))}`);
    console.log(`       Timeout: ${config.timeoutMs}ms | Retries: ${config.retryAttempts}`);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`  ❌  Config load failed: ${msg}`);
    console.error("\n  ⚠️  Ensure all CARESTACK_* env vars are set (see .env.example).");
    process.exit(1);
  }

  // ── 2. Instantiate adapter ─────────────────────────────────────────────────
  console.log("\n[ 2 ] Instantiating CareStackDirectAdapter...");
  const tenantId = process.env.ADAPTER_TENANT_ID ?? "validate-script-tenant";
  const adapter = new CareStackDirectAdapter(config, tenantId);
  console.log(`  ✅  Adapter instantiated for tenant: ${maskId(tenantId)}`);

  // ── 3. Health check (triggers OAuth2 token grant) ─────────────────────────
  console.log("\n[ 3 ] Running health check (triggers OAuth2 token grant)...");
  await check("healthCheck — OAuth2 token + API reachability", async () => {
    const health = await adapter.healthCheck();
    if (!health.healthy) {
      throw new Error(`Unhealthy: ${health.details?.error ?? "unknown error"}`);
    }
    return `adapter=${health.adapterType} | latency=${health.details?.latencyMs ?? "?"}ms`;
  });

  // ── 4. List patients (first page) ──────────────────────────────────────────
  console.log("\n[ 4 ] Listing patients (first page, limit=5)...");
  let firstPatient: CanonicalPatient | undefined;

  await check("listPatients — first page", async () => {
    const result = await adapter.listPatients({
      tenantId,
      limit: 5,
      offset: 0,
    });
    if (result.patients.length === 0) {
      throw new Error("listPatients returned 0 results — check CARESTACK_ACCOUNT_ID");
    }
    firstPatient = result.patients[0];
    const stages = result.patients.map(p => p.stage).join(", ");
    return `returned ${result.patients.length} patients (total: ${result.total}) | stages: [${stages}]`;
  });

  // ── 5. Get single patient chart ────────────────────────────────────────────
  console.log("\n[ 5 ] Fetching single patient chart (getPatient)...");
  let patientForHistory: CanonicalPatient | undefined;

  if (firstPatient) {
    await check(`getPatient — id: ${maskId(firstPatient.id)}`, async () => {
      const patient = await adapter.getPatient(firstPatient!.id, {
        purpose: "treatment",
        requestedBy: "validate-script",
        tenantId,
        patientId: firstPatient!.id,
        timestamp: new Date(),
      });
      if (!patient) throw new Error("getPatient returned null");
      patientForHistory = patient;
      const hasInsurance = (patient.insurance?.length ?? 0) > 0;
      const apptCount = patient.upcomingAppointments?.length ?? 0;
      return [
        `name: ${maskName(`${patient.firstName} ${patient.lastName}`)}`,
        `dob: ${patient.dateOfBirth ? patient.dateOfBirth.getFullYear() + "-**-**" : "none"}`,
        `stage: ${patient.stage}`,
        `insurance: ${hasInsurance ? "present" : "none"}`,
        `upcoming appts: ${apptCount}`,
      ].join(" | ");
    });
  } else {
    results.push({ name: "getPatient — skipped (no patient from listPatients)", passed: false, detail: "no patient id available", durationMs: 0 });
    console.warn("  ⚠️  Skipping getPatient — no patient returned from listPatients.");
  }

  const targetPatient = patientForHistory ?? firstPatient;

  // ── 6. Get treatment plans ─────────────────────────────────────────────────
  console.log("\n[ 6 ] Fetching treatment plans (getTreatmentPlans)...");
  let treatmentPlans: CanonicalTreatmentPlan[] = [];

  if (targetPatient) {
    await check(`getTreatmentPlans — patient: ${maskId(targetPatient.id)}`, async () => {
      treatmentPlans = await adapter.getTreatmentPlans(targetPatient!.id, {
        purpose: "treatment",
        requestedBy: "validate-script",
        tenantId,
        patientId: targetPatient!.id,
        timestamp: new Date(),
      });
      const unscheduled = treatmentPlans.filter(
        tp => tp.status === "proposed" || tp.status === "presented"
      );
      const accepted = treatmentPlans.filter(tp => tp.status === "accepted");
      const totalValue = treatmentPlans.reduce((sum, tp) => sum + (tp.totalFee ?? 0), 0);
      return [
        `${treatmentPlans.length} plans total`,
        `unscheduled (dormant pipeline): ${unscheduled.length}`,
        `accepted (cross-coding candidates): ${accepted.length}`,
        `total value: $${totalValue.toLocaleString()}`,
      ].join(" | ");
    });
  } else {
    results.push({ name: "getTreatmentPlans — skipped (no patient)", passed: false, detail: "no patient id available", durationMs: 0 });
    console.warn("  ⚠️  Skipping getTreatmentPlans — no patient available.");
  }

  // ── 7. Get medical history (ConditionIds from treatment plans) ─────────────
  console.log("\n[ 7 ] Fetching medical history (getMedicalHistory)...");

  if (targetPatient) {
    await check(`getMedicalHistory — patient: ${maskId(targetPatient.id)}`, async () => {
      const history: CanonicalMedicalHistory = await adapter.getMedicalHistory(
        targetPatient!.id,
        {
          purpose: "treatment",
          requestedBy: "validate-script",
          tenantId,
          patientId: targetPatient!.id,
          timestamp: new Date(),
        }
      );
      const condCount = history.conditions?.length ?? 0;
      const medCount = history.medications?.length ?? 0;
      const allergyCount = history.allergies?.length ?? 0;
      return [
        `conditions: ${condCount}`,
        `medications: ${medCount}`,
        `allergies: ${allergyCount}`,
        `ASA class: ${history.asaClassification ?? "not set"}`,
        `last updated: ${history.lastUpdated?.toISOString().slice(0, 10) ?? "unknown"}`,
      ].join(" | ");
    });
  } else {
    results.push({ name: "getMedicalHistory — skipped (no patient)", passed: false, detail: "no patient id available", durationMs: 0 });
    console.warn("  ⚠️  Skipping getMedicalHistory — no patient available.");
  }

  // ── 8. Summary ────────────────────────────────────────────────────────────
  console.log("\n═══════════════════════════════════════════════════════════════");
  console.log("  VALIDATION SUMMARY");
  console.log("═══════════════════════════════════════════════════════════════");

  const passed = results.filter(r => r.passed).length;
  const failed = results.filter(r => !r.passed).length;
  const totalMs = results.reduce((sum, r) => sum + r.durationMs, 0);

  console.log(`\n  Checks passed:  ${passed} / ${results.length}`);
  console.log(`  Checks failed:  ${failed}`);
  console.log(`  Total time:     ${totalMs}ms\n`);

  if (failed === 0) {
    console.log("  🟢  ALL CHECKS PASSED");
    console.log("  CareStackDirectAdapter is production-ready.");
    console.log("  AI agent intelligence loops can now pull real patient data.");
    console.log("  Set ADAPTER_TYPE=carestack_direct in .env to activate.\n");
  } else {
    console.error("  🔴  VALIDATION FAILED");
    console.error("  Fix the issues above before switching from mock data.\n");
    console.error("  Failed checks:");
    for (const r of results.filter(r => !r.passed)) {
      console.error(`    ❌  ${r.name}`);
      console.error(`         ${r.detail}`);
    }
    console.error("\n  Troubleshooting:");
    console.error("    1. Confirm all CARESTACK_* vars are set in .env");
    console.error("    2. Verify CLIENT_ID/SECRET with CareStack support");
    console.error("    3. Confirm CARESTACK_ACCOUNT_ID matches your practice");
    console.error("    4. Check that IDP and API URLs have no trailing slash");
    console.error("    5. Review ENG-538: procedure-codes LIST endpoint is unreliable\n");
    process.exit(1);
  }
}

main().catch((err: unknown) => {
  const msg = err instanceof Error ? err.message : String(err);
  console.error(`\n  💥  Unhandled error: ${msg}`);
  if (err instanceof Error && err.stack) {
    console.error(err.stack);
  }
  process.exit(1);
});

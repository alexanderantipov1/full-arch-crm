#!/usr/bin/env ts-node
/**
 * full-arch-crm — Adapter Switcher CLI
 * ──────────────────────────────────────
 * Switches the active adapter mode by rewriting .env, then verifies the
 * connection by running a live health check.
 *
 * Usage:
 *   npx ts-node scripts/switch-adapter.ts --type fusion_crm --url http://localhost:8000 --key YOUR_KEY
 *   npx ts-node scripts/switch-adapter.ts --type mock
 *
 * The script edits .env in the project root (one level up from scripts/).
 * If .env does not exist yet, it creates one from .env.example if present,
 * or starts from scratch.
 */

import * as fs from "fs";
import * as path from "path";

// Dynamically load adapter health after env is written so it picks up new vars.
// We do a deferred require inside the run() function below.

// ─── Arg parsing ─────────────────────────────────────────────────────────────

interface CliArgs {
  type: string;
  url?: string;
  key?: string;
}

function parseArgs(argv: string[]): CliArgs {
  const args: CliArgs = { type: "mock" };
  for (let i = 0; i < argv.length; i++) {
    switch (argv[i]) {
      case "--type":
        args.type = argv[++i] ?? "mock";
        break;
      case "--url":
        args.url = argv[++i];
        break;
      case "--key":
        args.key = argv[++i];
        break;
    }
  }
  return args;
}

// ─── .env file manipulation ───────────────────────────────────────────────────

type EnvMap = Map<string, { value: string; comment?: string }>;

/** Parse an .env file into an ordered map, preserving blank lines and comments. */
function parseEnvFile(content: string): string[] {
  return content.split("\n");
}

/** Set or add a key=value in the raw lines array from an .env file. */
function setEnvLine(lines: string[], key: string, value: string): string[] {
  const pattern = new RegExp(`^(#\\s*)?${key}=`);
  let found = false;

  const updated = lines.map((line) => {
    if (pattern.test(line) && !found) {
      found = true;
      return `${key}=${value}`;
    }
    return line;
  });

  if (!found) {
    updated.push(`${key}=${value}`);
  }

  return updated;
}

function writeEnvFile(envPath: string, lines: string[]): void {
  fs.writeFileSync(envPath, lines.join("\n"), "utf8");
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function run(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));

  const projectRoot = path.resolve(__dirname, "..");
  const envPath = path.join(projectRoot, ".env");
  const envExamplePath = path.join(projectRoot, ".env.example");

  // Ensure .env exists
  if (!fs.existsSync(envPath)) {
    if (fs.existsSync(envExamplePath)) {
      console.log("[switch-adapter] .env not found — copying from .env.example");
      fs.copyFileSync(envExamplePath, envPath);
    } else {
      console.log("[switch-adapter] .env not found — creating empty .env");
      fs.writeFileSync(envPath, "", "utf8");
    }
  }

  let lines = parseEnvFile(fs.readFileSync(envPath, "utf8"));

  // Always update ADAPTER_TYPE
  lines = setEnvLine(lines, "ADAPTER_TYPE", args.type);
  console.log(`[switch-adapter] Setting ADAPTER_TYPE=${args.type}`);

  if (args.type !== "mock") {
    if (args.url !== undefined) {
      lines = setEnvLine(lines, "FUSION_CRM_URL", args.url);
      console.log(`[switch-adapter] Setting FUSION_CRM_URL=${args.url}`);
    }
    if (args.key !== undefined) {
      lines = setEnvLine(lines, "FUSION_CRM_API_KEY", args.key);
      console.log(`[switch-adapter] Setting FUSION_CRM_API_KEY=***`);
    }
  }

  writeEnvFile(envPath, lines);
  console.log(`[switch-adapter] Wrote updated .env`);

  // Apply new env vars to this process so the health check picks them up
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eqIdx = trimmed.indexOf("=");
    if (eqIdx === -1) continue;
    const k = trimmed.slice(0, eqIdx).trim();
    const v = trimmed.slice(eqIdx + 1).trim();
    process.env[k] = v;
  }

  // Bootstrap adapters with the new env, then run health check
  try {
    // Use dynamic import so the bootstrapped adapters pick up the updated process.env
    const { bootstrapAdapters } = await import(
      path.join(projectRoot, "server", "adapters", "registry")
    );
    await bootstrapAdapters();

    const { checkAdapterHealth } = await import(
      path.join(projectRoot, "server", "adapters", "adapter-health")
    );

    const tenantId =
      process.env.ADAPTER_TENANT_ID ??
      process.env.DEFAULT_TENANT_ID ??
      "a1b2c3d4-e5f6-7890-abcd-ef1234567890";

    const health = await checkAdapterHealth(tenantId);

    console.log(
      `\nSwitched to ${health.adapterType} adapter — health: ${health.status} (${health.latencyMs}ms)`
    );

    if (health.error) {
      console.error(`  Error: ${health.error}`);
    }

    process.exit(health.status === "offline" ? 1 : 0);
  } catch (err: any) {
    console.error(`[switch-adapter] Health check failed: ${err?.message ?? err}`);
    process.exit(1);
  }
}

run();

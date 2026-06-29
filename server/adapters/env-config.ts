/**
 * full-arch-crm — Central Env Config Validator
 * ─────────────────────────────────────────────
 * Single source of truth for all environment variable validation.
 * Called once at startup; result is cached for the lifetime of the process.
 *
 * Graceful-fallback rule (mirrors registry.ts intent):
 *   If ADAPTER_TYPE=fusion_crm and FUSION_CRM_URL is missing → warn + fall back to mock.
 *   For other missing vars we log a warning but do NOT auto-fall back — callers decide.
 */

// ─── Types ────────────────────────────────────────────────────────────────────

export type AdapterType =
  | "fusion_crm"
  | "mock"
  | "western_dental"
  | "clearchoice"
  | "generic_rest"
  | "carestack_direct";

export interface EnvConfig {
  adapterType: AdapterType;
  fusionCrmUrl: string;
  fusionCrmApiKey: string;
  tenantId: string;
  nodeEnv: "development" | "production" | "test";
  /** true when adapterType is anything other than 'mock' */
  isLiveMode: boolean;
  /** list of required env vars that are unset for the configured adapter */
  missingVars: string[];
}

// ─── Required-var matrix ──────────────────────────────────────────────────────

const REQUIRED_VARS_BY_ADAPTER: Record<AdapterType, string[]> = {
  fusion_crm: ["FUSION_CRM_URL", "FUSION_CRM_API_KEY", "ADAPTER_TENANT_ID"],
  western_dental: ["WESTERN_DENTAL_URL", "WESTERN_DENTAL_API_KEY", "ADAPTER_TENANT_ID"],
  clearchoice: ["CLEARCHOICE_URL", "CLEARCHOICE_API_KEY", "ADAPTER_TENANT_ID"],
  generic_rest: ["ADAPTER_URL", "ADAPTER_API_KEY", "ADAPTER_TENANT_ID"],
  carestack_direct: [
    "CARESTACK_IDP_BASE_URL",
    "CARESTACK_API_BASE_URL",
    "CARESTACK_CLIENT_ID",
    "CARESTACK_CLIENT_SECRET",
    "CARESTACK_VENDOR_KEY",
    "CARESTACK_ACCOUNT_KEY",
    "CARESTACK_ACCOUNT_ID",
    "ADAPTER_TENANT_ID",
  ],
  mock: [],
};

// ─── Loader ───────────────────────────────────────────────────────────────────

/**
 * Reads process.env, validates required vars, logs warnings for missing ones.
 *
 * Does NOT throw — returns a config with missingVars populated so callers can
 * decide how hard to fail.
 */
export function loadEnvConfig(): EnvConfig {
  const rawAdapterType = (process.env.ADAPTER_TYPE ?? "mock").trim() as AdapterType;

  // ── Validate adapterType ──────────────────────────────────────────────────
  const validAdapterTypes: AdapterType[] = [
    "fusion_crm",
    "mock",
    "western_dental",
    "clearchoice",
    "generic_rest",
    "carestack_direct",
  ];

  let adapterType: AdapterType = validAdapterTypes.includes(rawAdapterType)
    ? rawAdapterType
    : "mock";

  if (!validAdapterTypes.includes(rawAdapterType)) {
    console.warn(
      `[EnvConfig] Unknown ADAPTER_TYPE="${rawAdapterType}". ` +
        `Valid types: ${validAdapterTypes.join(", ")}. Falling back to "mock".`
    );
  }

  const fusionCrmUrl = process.env.FUSION_CRM_URL ?? "";
  const fusionCrmApiKey = process.env.FUSION_CRM_API_KEY ?? process.env.FUSION_API_KEY ?? "";
  const tenantId =
    process.env.ADAPTER_TENANT_ID ??
    process.env.DEFAULT_TENANT_ID ??
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890";

  const rawNodeEnv = (process.env.NODE_ENV ?? "development") as EnvConfig["nodeEnv"];
  const validNodeEnvs: Array<EnvConfig["nodeEnv"]> = ["development", "production", "test"];
  const nodeEnv: EnvConfig["nodeEnv"] = validNodeEnvs.includes(rawNodeEnv)
    ? rawNodeEnv
    : "development";

  // ── Check required vars for the chosen adapter ───────────────────────────
  const requiredVars = REQUIRED_VARS_BY_ADAPTER[adapterType] ?? [];
  const missingVars: string[] = [];

  for (const varName of requiredVars) {
    if (!process.env[varName]) {
      console.warn(`[EnvConfig] Missing required env var for adapter "${adapterType}": ${varName}`);
      missingVars.push(varName);
    }
  }

  // ── Graceful fallback: fusion_crm without FUSION_CRM_URL → mock ──────────
  if (adapterType === "fusion_crm" && !fusionCrmUrl) {
    console.error(
      "[EnvConfig] ADAPTER_TYPE=fusion_crm but FUSION_CRM_URL is not set. " +
        "Falling back to mock adapter to prevent a crashed startup. " +
        "Set FUSION_CRM_URL to connect to a live Fusion CRM instance."
    );
    adapterType = "mock";
  }

  const isLiveMode = adapterType !== "mock";

  if (isLiveMode) {
    console.log(`[EnvConfig] Live mode active — adapter: ${adapterType}, tenant: ${tenantId}`);
  } else {
    console.log(`[EnvConfig] Mock mode active (no live data calls will be made)`);
  }

  return {
    adapterType,
    fusionCrmUrl,
    fusionCrmApiKey,
    tenantId,
    nodeEnv,
    isLiveMode,
    missingVars,
  };
}

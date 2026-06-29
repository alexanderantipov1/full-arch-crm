/**
 * full-arch-crm — Adapter Registry
 * ─────────────────────────────────
 * Single source of truth for all active adapters.
 * AI modules call registry.getAdapter(tenantId) — never import adapters directly.
 *
 * Multi-clinic routing: one process can serve multiple tenants simultaneously.
 * Each tenant has its own adapter instance with its own credentials.
 */

import type { DatabaseAdapter } from "./interface";
import type { AdapterType, CanonicalTenant } from "./types";

class AdapterRegistry {
  private adapters = new Map<string, DatabaseAdapter>();  // tenantId → adapter
  private tenants = new Map<string, CanonicalTenant>();   // tenantId → tenant config

  /**
   * Register an adapter for a tenant.
   * Called once at startup per configured tenant.
   */
  register(tenantId: string, adapter: DatabaseAdapter, tenant: CanonicalTenant): void {
    if (this.adapters.has(tenantId)) {
      console.warn(`[AdapterRegistry] Overwriting adapter for tenant ${tenantId}`);
    }
    this.adapters.set(tenantId, adapter);
    this.tenants.set(tenantId, tenant);
    console.log(`[AdapterRegistry] Registered adapter: ${adapter.adapterType} → tenant: ${tenantId}`);
  }

  /**
   * Get the adapter for a tenant. Throws if tenant not found.
   * This is the only way AI modules should access data.
   */
  getAdapter(tenantId: string): DatabaseAdapter {
    const adapter = this.adapters.get(tenantId);
    if (!adapter) {
      throw new AdapterNotFoundError(tenantId, [...this.adapters.keys()]);
    }
    return adapter;
  }

  /**
   * Get adapter by type (convenience — returns first match).
   * Used when tenantId is not yet known.
   */
  getAdapterByType(type: AdapterType): DatabaseAdapter | undefined {
    for (const [, adapter] of this.adapters) {
      if (adapter.adapterType === type) return adapter;
    }
    return undefined;
  }

  /**
   * Get the default adapter (first registered, or env-configured tenant).
   * Used for single-tenant deployments.
   */
  getDefaultAdapter(): DatabaseAdapter {
    const defaultTenantId = process.env.DEFAULT_TENANT_ID;
    if (defaultTenantId) {
      return this.getAdapter(defaultTenantId);
    }
    const first = this.adapters.values().next().value;
    if (!first) {
      throw new Error("[AdapterRegistry] No adapters registered. Check startup configuration.");
    }
    return first;
  }

  getTenant(tenantId: string): CanonicalTenant | undefined {
    return this.tenants.get(tenantId);
  }

  listTenants(): CanonicalTenant[] {
    return [...this.tenants.values()];
  }

  listAdapterTypes(): AdapterType[] {
    return [...new Set([...this.adapters.values()].map(a => a.adapterType as AdapterType))];
  }

  hasAdapter(tenantId: string): boolean {
    return this.adapters.has(tenantId);
  }

  deregister(tenantId: string): void {
    this.adapters.delete(tenantId);
    this.tenants.delete(tenantId);
  }

  /** Run healthCheck on all registered adapters */
  async healthCheckAll(): Promise<Record<string, boolean>> {
    const results: Record<string, boolean> = {};
    await Promise.allSettled(
      [...this.adapters.entries()].map(async ([tenantId, adapter]) => {
        try {
          const health = await adapter.healthCheck();
          results[tenantId] = health.healthy;
        } catch {
          results[tenantId] = false;
        }
      })
    );
    return results;
  }
}

export class AdapterNotFoundError extends Error {
  constructor(tenantId: string, registered: string[]) {
    super(
      `No adapter registered for tenant "${tenantId}". ` +
      `Registered tenants: [${registered.join(", ") || "none"}]. ` +
      `Check ADAPTER_TENANT_ID env var and startup configuration.`
    );
    this.name = "AdapterNotFoundError";
  }
}

// ─── Singleton ────────────────────────────────────────────────────────────────

export const adapterRegistry = new AdapterRegistry();

// ─── Startup bootstrap ────────────────────────────────────────────────────────

/**
 * Called once at server startup (server/app.ts).
 * Reads env vars, instantiates the correct adapter, registers it.
 *
 * To add a new DSO:
 * 1. Add their AdapterType to types.ts
 * 2. Add their adapter class import below
 * 3. Add their env var block
 * Done — no other changes needed.
 */
export async function bootstrapAdapters(): Promise<void> {
  const adapterType = (process.env.ADAPTER_TYPE ?? "mock") as AdapterType;
  const tenantId = process.env.ADAPTER_TENANT_ID ?? "a1b2c3d4-e5f6-7890-abcd-ef1234567890";

  console.log(`[AdapterRegistry] Bootstrapping adapter: type=${adapterType} tenant=${tenantId}`);

  let adapter: DatabaseAdapter;

  switch (adapterType) {
    case "fusion_crm": {
      const { FusionCrmAdapter } = await import("./implementations/fusion-crm-adapter");
      adapter = new FusionCrmAdapter({
        baseUrl: process.env.FUSION_CRM_URL ?? "http://localhost:8000",
        apiKey: process.env.FUSION_API_KEY ?? "",
        tenantId,
        timeoutMs: 10000,
        retryAttempts: 3,
      }, tenantId);
      break;
    }

    case "carestack_direct": {
      const { CareStackDirectAdapter, careStackConfigFromEnv } =
        await import("./implementations/carestack-direct-adapter");
      const csConfig = careStackConfigFromEnv();
      adapter = new CareStackDirectAdapter(csConfig, tenantId);
      break;
    }

    case "mock":
    default: {
      const { MockAdapter } = await import("./implementations/mock-adapter");
      adapter = new MockAdapter(tenantId);
      break;
    }

    // ── Future DSOs ────────────────────────────────────────────────────────
    // case "western_dental": {
    //   const { WesternDentalAdapter } = await import("./implementations/western-dental-adapter");
    //   adapter = new WesternDentalAdapter({ ...config }, tenantId);
    //   break;
    // }
    // case "clearchoice": { ... }
    // case "novvia": { ... }
  }

  const tenant: CanonicalTenant = {
    tenantId,
    slug: process.env.TENANT_SLUG ?? "default",
    displayName: process.env.TENANT_NAME ?? "Fusion Dental",
    adapterType,
    adapterConfig: { baseUrl: process.env.FUSION_CRM_URL },
    hipaaConfig: {
      baaSignedAt: process.env.ANTHROPIC_BAA_SIGNED === "true" ? new Date() : undefined,
      phiAccessLogEnabled: true,
      auditRetentionDays: 2190, // 6 years — HIPAA minimum
      encryptionAtRest: true,
      encryptionInTransit: true,
      allowedPurposes: ["treatment", "payment", "operations", "ai_scribe", "insurance_verification", "audit"],
    },
    createdAt: new Date(),
    enabled: true,
  };

  adapterRegistry.register(tenantId, adapter, tenant);
  console.log(`[AdapterRegistry] Bootstrap complete — adapter ready for tenant: ${tenantId}`);
}

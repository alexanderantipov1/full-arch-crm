/**
 * full-arch-crm — Adapter Health Check
 * ─────────────────────────────────────
 * Tests the configured adapter by making a minimal live call (fetch 1 patient).
 * Used by the /api/health/adapter endpoint and the switch-adapter CLI script.
 */

import { adapterRegistry } from "./registry";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AdapterHealth {
  adapterType: string;
  status: "healthy" | "degraded" | "offline";
  latencyMs: number;
  tenantId: string;
  testedAt: string;
  error?: string;
}

// ─── Health check ─────────────────────────────────────────────────────────────

/**
 * Tests the configured adapter for the given tenantId.
 *
 * Strategy:
 * 1. Try the adapter's own healthCheck() method first (cheap ping).
 * 2. If healthy, confirm with a minimal listPatients(limit=1) call so we know
 *    the data path is actually working, not just the network socket.
 * 3. Classify latency: <500 ms → healthy, 500–2000 ms → degraded, error → offline.
 */
export async function checkAdapterHealth(tenantId: string): Promise<AdapterHealth> {
  const testedAt = new Date().toISOString();
  let adapter;

  try {
    adapter = adapterRegistry.getAdapter(tenantId);
  } catch (err: any) {
    return {
      adapterType: "unknown",
      status: "offline",
      latencyMs: 0,
      tenantId,
      testedAt,
      error: err?.message ?? "Adapter not registered for this tenantId",
    };
  }

  const start = Date.now();

  try {
    // Primary: use the adapter's built-in healthCheck (fast ping)
    const health = await adapter.healthCheck();
    const latencyMs = Date.now() - start;

    if (!health.healthy) {
      return {
        adapterType: adapter.adapterType,
        status: "offline",
        latencyMs,
        tenantId,
        testedAt,
        error: health.error ?? "Adapter reported unhealthy",
      };
    }

    // Secondary: make a real data call to confirm the full path works
    const dataStart = Date.now();
    await adapter.listPatients({ limit: 1 });
    const totalLatencyMs = Date.now() - start;

    const status: AdapterHealth["status"] =
      totalLatencyMs < 500 ? "healthy" : totalLatencyMs < 2000 ? "degraded" : "offline";

    return {
      adapterType: adapter.adapterType,
      status,
      latencyMs: totalLatencyMs,
      tenantId,
      testedAt,
    };
  } catch (err: any) {
    const latencyMs = Date.now() - start;
    return {
      adapterType: adapter.adapterType,
      status: "offline",
      latencyMs,
      tenantId,
      testedAt,
      error: err?.message ?? "Unknown error during health check",
    };
  }
}

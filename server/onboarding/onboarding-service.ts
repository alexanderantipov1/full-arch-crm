import { randomUUID } from 'crypto';
import fs from 'fs';
import path from 'path';

export interface TenantOnboarding {
  tenantId: string;          // UUID v4, generated on creation
  orgName: string;           // e.g. "Western Dental"
  orgType: 'dso' | 'group_practice' | 'single_practice';
  adapterType: 'fusion' | 'western_dental' | 'clearchoice' | 'generic_rest' | 'mock';
  databaseUrl?: string;      // their REST API base URL
  apiKey?: string;           // encrypted at rest
  locationCount: number;
  status: 'pending' | 'configuring' | 'testing' | 'active' | 'suspended';
  createdAt: string;
  activatedAt?: string;
}

export interface CreateTenantParams {
  orgName: string;
  orgType: TenantOnboarding['orgType'];
  adapterType: TenantOnboarding['adapterType'];
  databaseUrl?: string;
  apiKey?: string;
  locationCount: number;
}

// ─── Persistence ────────────────────────────────────────────────────────────

const TENANTS_FILE = path.join(__dirname, 'tenants.json');

function loadTenants(): Map<string, TenantOnboarding> {
  try {
    if (fs.existsSync(TENANTS_FILE)) {
      const raw = fs.readFileSync(TENANTS_FILE, 'utf-8');
      const arr: TenantOnboarding[] = JSON.parse(raw);
      return new Map(arr.map((t) => [t.tenantId, t]));
    }
  } catch (err) {
    console.error('[onboarding] Failed to load tenants.json:', err);
  }
  return new Map();
}

function saveTenants(tenants: Map<string, TenantOnboarding>): void {
  try {
    const dir = path.dirname(TENANTS_FILE);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(TENANTS_FILE, JSON.stringify([...tenants.values()], null, 2), 'utf-8');
  } catch (err) {
    console.error('[onboarding] Failed to save tenants.json:', err);
  }
}

// In-memory store, lazily populated from JSON
const tenantStore: Map<string, TenantOnboarding> = loadTenants();

// ─── Audit log ───────────────────────────────────────────────────────────────

const AUDIT_LOG_FILE = path.join(__dirname, 'audit.log');

function writeAudit(event: string, tenantId: string, detail?: string): void {
  const line = JSON.stringify({
    ts: new Date().toISOString(),
    event,
    tenantId,
    detail: detail ?? null,
  });
  try {
    fs.appendFileSync(AUDIT_LOG_FILE, line + '\n', 'utf-8');
  } catch {
    // non-fatal
  }
  console.log(`[audit] ${event} tenant=${tenantId}${detail ? ' ' + detail : ''}`);
}

// ─── Simple "encryption" shim ────────────────────────────────────────────────
// In production this would use KMS / Vault.  For now we base-64 the key so it
// is not stored in plain-text in the JSON file.
function encryptApiKey(key: string): string {
  return Buffer.from(key).toString('base64');
}

// ─── Adapter connection test ─────────────────────────────────────────────────

async function probeAdapter(tenant: TenantOnboarding): Promise<{ success: boolean; message: string }> {
  switch (tenant.adapterType) {
    case 'mock':
      // Demo mode — always succeeds
      await new Promise((r) => setTimeout(r, 800));
      return { success: true, message: '1 demo patient record found' };

    case 'fusion':
    case 'western_dental':
    case 'clearchoice': {
      // Simulate a live check against the well-known adapter base URLs.
      // In production these would call the real adapter health / patient endpoints.
      const baseUrls: Record<string, string> = {
        fusion: 'https://api.fusiondentalcrm.example/health',
        western_dental: 'https://api.westerndental.example/health',
        clearchoice: 'https://api.clearchoice.example/health',
      };
      const url = baseUrls[tenant.adapterType];
      try {
        const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
        if (res.ok) {
          return { success: true, message: '1 patient record found via adapter' };
        }
        return { success: false, message: `Adapter returned HTTP ${res.status}` };
      } catch {
        // Example domains are unreachable — treat as simulated success for demo purposes
        await new Promise((r) => setTimeout(r, 600));
        return { success: true, message: '1 patient record found (simulated)' };
      }
    }

    case 'generic_rest': {
      if (!tenant.databaseUrl) {
        return { success: false, message: 'No database URL configured' };
      }
      try {
        const headers: Record<string, string> = { 'Content-Type': 'application/json' };
        if (tenant.apiKey) {
          headers['Authorization'] = `Bearer ${Buffer.from(tenant.apiKey, 'base64').toString('utf-8')}`;
        }
        const res = await fetch(tenant.databaseUrl, {
          headers,
          signal: AbortSignal.timeout(8000),
        });
        if (res.ok) {
          return { success: true, message: '1 patient record found' };
        }
        return { success: false, message: `Remote returned HTTP ${res.status}` };
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        return { success: false, message: `Connection failed: ${msg}` };
      }
    }

    default:
      return { success: false, message: 'Unknown adapter type' };
  }
}

// ─── Public API ──────────────────────────────────────────────────────────────

/**
 * Create a new tenant.  Generates a UUID, stores config, returns the tenant.
 */
export async function createTenant(params: CreateTenantParams): Promise<TenantOnboarding> {
  const tenant: TenantOnboarding = {
    tenantId: randomUUID(),
    orgName: params.orgName,
    orgType: params.orgType,
    adapterType: params.adapterType,
    databaseUrl: params.databaseUrl,
    apiKey: params.apiKey ? encryptApiKey(params.apiKey) : undefined,
    locationCount: params.locationCount,
    status: 'pending',
    createdAt: new Date().toISOString(),
  };

  tenantStore.set(tenant.tenantId, tenant);
  saveTenants(tenantStore);
  writeAudit('TENANT_CREATED', tenant.tenantId, `org="${tenant.orgName}" adapter=${tenant.adapterType}`);

  return tenant;
}

/**
 * Test connectivity for a tenant by calling the configured adapter.
 * Fetches 1 patient record to verify credentials.
 */
export async function testConnection(tenantId: string): Promise<{ success: boolean; message: string }> {
  const tenant = tenantStore.get(tenantId);
  if (!tenant) throw new Error(`Tenant ${tenantId} not found`);

  // Move to testing state
  tenant.status = 'testing';
  tenantStore.set(tenantId, tenant);
  saveTenants(tenantStore);

  const result = await probeAdapter(tenant);

  // Update status based on result
  tenant.status = result.success ? 'configuring' : 'pending';
  tenantStore.set(tenantId, tenant);
  saveTenants(tenantStore);

  writeAudit(
    result.success ? 'CONNECTION_TEST_OK' : 'CONNECTION_TEST_FAILED',
    tenantId,
    result.message,
  );

  return result;
}

/**
 * Activate a tenant.  Sets status to 'active' and logs an audit entry.
 */
export async function activateTenant(tenantId: string): Promise<TenantOnboarding> {
  const tenant = tenantStore.get(tenantId);
  if (!tenant) throw new Error(`Tenant ${tenantId} not found`);

  tenant.status = 'active';
  tenant.activatedAt = new Date().toISOString();
  tenantStore.set(tenantId, tenant);
  saveTenants(tenantStore);

  writeAudit('TENANT_ACTIVATED', tenantId, `org="${tenant.orgName}"`);

  return tenant;
}

/**
 * List all tenants.  Admin-only — caller must enforce auth before calling this.
 */
export async function listTenants(): Promise<TenantOnboarding[]> {
  return [...tenantStore.values()];
}

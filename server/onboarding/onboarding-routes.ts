import { Router, Request, Response, NextFunction } from 'express';
import {
  createTenant,
  testConnection,
  activateTenant,
  listTenants,
  CreateTenantParams,
  TenantOnboarding,
} from './onboarding-service';

const router = Router();

// ─── Helpers ─────────────────────────────────────────────────────────────────

function asyncHandler(fn: (req: Request, res: Response, next: NextFunction) => Promise<void>) {
  return (req: Request, res: Response, next: NextFunction) => {
    fn(req, res, next).catch(next);
  };
}

function validateOrgType(v: unknown): v is TenantOnboarding['orgType'] {
  return v === 'dso' || v === 'group_practice' || v === 'single_practice';
}

function validateAdapterType(v: unknown): v is TenantOnboarding['adapterType'] {
  return (
    v === 'fusion' ||
    v === 'western_dental' ||
    v === 'clearchoice' ||
    v === 'generic_rest' ||
    v === 'mock'
  );
}

// ─── Routes ──────────────────────────────────────────────────────────────────

/**
 * POST /api/onboarding/tenant
 * Create a new tenant onboarding record.
 *
 * Body:
 *   orgName       string   required
 *   orgType       string   required  ('dso' | 'group_practice' | 'single_practice')
 *   adapterType   string   required  ('fusion' | 'western_dental' | 'clearchoice' | 'generic_rest' | 'mock')
 *   databaseUrl   string   optional  (required when adapterType === 'generic_rest')
 *   apiKey        string   optional
 *   locationCount number   required
 */
router.post(
  '/tenant',
  asyncHandler(async (req, res) => {
    const { orgName, orgType, adapterType, databaseUrl, apiKey, locationCount } = req.body as Record<string, unknown>;

    // Validation
    if (!orgName || typeof orgName !== 'string' || orgName.trim().length === 0) {
      res.status(400).json({ error: 'orgName is required' });
      return;
    }
    if (!validateOrgType(orgType)) {
      res.status(400).json({ error: 'orgType must be dso | group_practice | single_practice' });
      return;
    }
    if (!validateAdapterType(adapterType)) {
      res.status(400).json({
        error: 'adapterType must be fusion | western_dental | clearchoice | generic_rest | mock',
      });
      return;
    }
    if (adapterType === 'generic_rest' && (!databaseUrl || typeof databaseUrl !== 'string')) {
      res.status(400).json({ error: 'databaseUrl is required for generic_rest adapter' });
      return;
    }
    const locCount = Number(locationCount);
    if (!Number.isInteger(locCount) || locCount < 1) {
      res.status(400).json({ error: 'locationCount must be a positive integer' });
      return;
    }

    const params: CreateTenantParams = {
      orgName: (orgName as string).trim(),
      orgType,
      adapterType,
      databaseUrl: typeof databaseUrl === 'string' ? databaseUrl.trim() : undefined,
      apiKey: typeof apiKey === 'string' ? apiKey : undefined,
      locationCount: locCount,
    };

    const tenant = await createTenant(params);
    res.status(201).json({ tenant });
  }),
);

/**
 * POST /api/onboarding/tenant/:id/test
 * Test the database connection for a tenant.
 */
router.post(
  '/tenant/:id/test',
  asyncHandler(async (req, res) => {
    const { id } = req.params;
    try {
      const result = await testConnection(id);
      res.status(result.success ? 200 : 422).json(result);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      if (msg.includes('not found')) {
        res.status(404).json({ error: msg });
      } else {
        res.status(500).json({ error: msg });
      }
    }
  }),
);

/**
 * POST /api/onboarding/tenant/:id/activate
 * Activate a tenant after a successful connection test.
 */
router.post(
  '/tenant/:id/activate',
  asyncHandler(async (req, res) => {
    const { id } = req.params;
    try {
      const tenant = await activateTenant(id);
      res.json({ tenant });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      if (msg.includes('not found')) {
        res.status(404).json({ error: msg });
      } else {
        res.status(500).json({ error: msg });
      }
    }
  }),
);

/**
 * GET /api/onboarding/tenants
 * List all tenants.  Requires admin header: X-Admin-Key.
 *
 * In production this would be protected by a proper auth middleware;
 * for now a simple env-var check guards the endpoint.
 */
router.get(
  '/tenants',
  asyncHandler(async (req, res) => {
    const adminKey = process.env.ADMIN_API_KEY;
    if (adminKey && req.headers['x-admin-key'] !== adminKey) {
      res.status(401).json({ error: 'Unauthorized — X-Admin-Key header required' });
      return;
    }
    const tenants = await listTenants();
    res.json({ tenants });
  }),
);

export default router;

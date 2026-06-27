/**
 * HIPAA Audit Middleware
 *
 * Express middleware that automatically logs all API requests touching
 * Protected Health Information (PHI). Attach this middleware to any router
 * that serves PHI routes.
 *
 * Covered route prefixes (configurable via PHI_ROUTE_PREFIXES env var):
 *   - /api/patients/*
 *   - /api/appointments/*
 *   - /api/claims/*
 *
 * Action mapping:
 *   GET    → READ
 *   POST   → WRITE
 *   PUT    → WRITE
 *   PATCH  → WRITE
 *   DELETE → DELETE
 *
 * Outcome mapping:
 *   2xx → SUCCESS
 *   401/403 → DENIED
 *   5xx → FAILURE
 *   other → FAILURE
 */

import { Request, Response, NextFunction } from 'express';
import { v4 as uuidv4 } from 'uuid';
import { AuditLogger, AuditAction, AuditOutcome } from './audit-logger.js';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * Route prefixes that carry PHI and must be audited.
 * Override at runtime with PHI_ROUTE_PREFIXES (comma-separated).
 */
const DEFAULT_PHI_PREFIXES = [
  '/api/patients',
  '/api/appointments',
  '/api/claims',
];

function phiPrefixes(): string[] {
  const env = process.env.PHI_ROUTE_PREFIXES;
  if (env) return env.split(',').map((p) => p.trim());
  return DEFAULT_PHI_PREFIXES;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function methodToAction(method: string): AuditAction {
  switch (method.toUpperCase()) {
    case 'GET':
    case 'HEAD':
      return 'READ';
    case 'POST':
      return 'WRITE';
    case 'PUT':
    case 'PATCH':
      return 'WRITE';
    case 'DELETE':
      return 'DELETE';
    default:
      return 'QUERY';
  }
}

function statusToOutcome(statusCode: number): AuditOutcome {
  if (statusCode >= 200 && statusCode < 300) return 'SUCCESS';
  if (statusCode === 401 || statusCode === 403) return 'DENIED';
  return 'FAILURE';
}

/**
 * Extracts a resource type and optional resource ID from a path.
 *
 * Examples:
 *   /api/patients        → { resource: 'patient',     resourceId: '' }
 *   /api/patients/123    → { resource: 'patient',     resourceId: '123' }
 *   /api/appointments/7  → { resource: 'appointment', resourceId: '7'  }
 *   /api/claims/abc-456  → { resource: 'claim',       resourceId: 'abc-456' }
 */
function extractResource(urlPath: string): { resource: string; resourceId: string } {
  // Strip query string
  const cleanPath = urlPath.split('?')[0];
  // Split on /
  const parts = cleanPath.split('/').filter(Boolean);
  // parts[0] = 'api', parts[1] = plural resource name, parts[2] = optional ID

  const pluralName = parts[1] ?? 'unknown';
  // Naïve singularisation: strip trailing 's'
  const resource = pluralName.endsWith('s')
    ? pluralName.slice(0, -1)
    : pluralName;

  const resourceId = parts[2] ?? '';
  return { resource, resourceId };
}

/**
 * Returns true if the request path starts with one of the PHI prefixes.
 */
function isPhiRoute(urlPath: string): boolean {
  const cleanPath = urlPath.split('?')[0];
  return phiPrefixes().some((prefix) => cleanPath.startsWith(prefix));
}

// ---------------------------------------------------------------------------
// Middleware
// ---------------------------------------------------------------------------

/**
 * Express middleware that logs PHI access events to the HIPAA audit trail.
 *
 * Mount this middleware at the application level (before your routers) so it
 * intercepts all PHI-touching routes automatically:
 *
 * ```typescript
 * import { auditMiddleware } from './audit/audit-middleware.js';
 * app.use(auditMiddleware);
 * ```
 *
 * Or mount it directly on the affected routers:
 *
 * ```typescript
 * patientRouter.use(auditMiddleware);
 * ```
 */
export function auditMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  // Skip non-PHI routes immediately — zero overhead for non-clinical APIs
  if (!isPhiRoute(req.path)) {
    next();
    return;
  }

  // ── Identity & correlation ──────────────────────────────────────────────
  const requestId =
    (req.headers['x-request-id'] as string | undefined) ?? uuidv4();
  const tenantId =
    (req.headers['x-tenant-id'] as string | undefined) ?? 'unknown';

  // Attach generated requestId to response headers for client-side correlation
  res.setHeader('x-request-id', requestId);

  // ── User identity ───────────────────────────────────────────────────────
  // Assumes authentication middleware (e.g. Passport, JWT) has populated
  // req.user. Falls back to 'anonymous' for unauthenticated requests — those
  // will result in DENIED outcomes and should alert ops.
  const userId: string =
    (req as Request & { user?: { id?: string; userId?: string } }).user?.id ??
    (req as Request & { user?: { id?: string; userId?: string } }).user?.userId ??
    'anonymous';

  // ── Resource ────────────────────────────────────────────────────────────
  const { resource, resourceId } = extractResource(req.path);
  const action = methodToAction(req.method);

  // ── Network metadata ────────────────────────────────────────────────────
  const ipAddress =
    (req.headers['x-forwarded-for'] as string | undefined)?.split(',')[0]?.trim() ??
    req.socket?.remoteAddress;
  const userAgent = req.headers['user-agent'];

  // ── Intercept response finish to capture outcome ────────────────────────
  const originalEnd = res.end.bind(res);

  // @ts-ignore — we're monkey-patching res.end to capture the status code
  res.end = function auditedEnd(
    ...args: Parameters<typeof res.end>
  ): ReturnType<typeof res.end> {
    const outcome = statusToOutcome(res.statusCode);

    AuditLogger.log({
      requestId,
      tenantId,
      userId,
      action,
      resource,
      resourceId,
      outcome,
      ipAddress,
      userAgent,
      // phiFields and reason can be enriched by individual route handlers
      // by setting res.locals.auditPhiFields / res.locals.auditReason before
      // calling next() or ending the response.
      phiFields: res.locals.auditPhiFields as string[] | undefined,
      reason: res.locals.auditReason as string | undefined,
    });

    // Restore original end
    res.end = originalEnd;
    return originalEnd(...args);
  };

  next();
}

// ---------------------------------------------------------------------------
// Per-route enrichment helpers
// ---------------------------------------------------------------------------

/**
 * Sets PHI field names that were accessed in this request.
 * Call from a route handler BEFORE sending the response.
 *
 * @example
 * router.get('/patients/:id', (req, res) => {
 *   setAuditPhiFields(res, ['firstName', 'lastName', 'dateOfBirth', 'ssn']);
 *   // ... fetch and return patient
 * });
 */
export function setAuditPhiFields(res: Response, fields: string[]): void {
  res.locals.auditPhiFields = fields;
}

/**
 * Sets a business justification for sensitive queries.
 * Call from a route handler BEFORE sending the response.
 *
 * @example
 * router.get('/patients/:id/full-record', (req, res) => {
 *   setAuditReason(res, 'Emergency care access by on-call physician');
 *   // ...
 * });
 */
export function setAuditReason(res: Response, reason: string): void {
  res.locals.auditReason = reason;
}

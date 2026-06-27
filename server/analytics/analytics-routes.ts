/**
 * DSO Analytics Routes
 * ────────────────────
 * Public REST endpoints for DSO partner BI tool integration.
 * Mounted at /api/analytics.
 *
 * All routes:
 *   - Require X-Tenant-ID header (400 if missing)
 *   - Return Content-Type: application/json
 *   - Add Cache-Control: max-age=300 (5-min BI cache)
 *   - Log to AuditLogger with action='QUERY', resource='analytics'
 *   - Return consistent error shape: { error: string, code: string }
 */

import { Router, type Request, type Response } from "express";
import { randomUUID } from "crypto";
import { AnalyticsService } from "./analytics-service";
import { AuditLogger } from "../audit/audit-logger";

export const analyticsRouter = Router();

// ─── Middleware helpers ───────────────────────────────────────────────────────

/** Extract and validate X-Tenant-ID; returns null and writes 400 on failure. */
function requireTenantId(req: Request, res: Response): string | null {
  const tenantId = req.headers["x-tenant-id"];
  if (!tenantId || typeof tenantId !== "string" || tenantId.trim() === "") {
    res.status(400).json({
      error: "Missing or empty X-Tenant-ID header",
      code: "MISSING_TENANT_ID",
    });
    return null;
  }
  return tenantId.trim();
}

/** Emit a HIPAA audit log entry for every analytics query. */
function auditQuery(
  tenantId: string,
  endpoint: string,
  outcome: "SUCCESS" | "FAILURE",
  req: Request
): void {
  AuditLogger.log({
    requestId: randomUUID(),
    tenantId,
    userId: (req as any).user?.id ?? "api-client",
    action: "QUERY",
    resource: "analytics",
    resourceId: endpoint,
    outcome,
    ipAddress: req.ip,
    userAgent: req.headers["user-agent"],
    reason: "DSO partner BI query",
  });
}

/** Apply shared response headers for all analytics endpoints. */
function analyticsHeaders(res: Response): void {
  res.setHeader("Content-Type", "application/json");
  res.setHeader("Cache-Control", "max-age=300");
}

// ─── GET /api/analytics/kpi ───────────────────────────────────────────────────

/**
 * Full KPI snapshot for the tenant.
 *
 * Returns: KPISnapshot
 *
 * Example:
 *   curl -H "X-Tenant-ID: <tenantId>" /api/analytics/kpi
 */
analyticsRouter.get("/kpi", async (req: Request, res: Response) => {
  const tenantId = requireTenantId(req, res);
  if (!tenantId) return;

  analyticsHeaders(res);

  try {
    const snapshot = await AnalyticsService.getKPISnapshot(tenantId);
    auditQuery(tenantId, "kpi", "SUCCESS", req);
    res.json(snapshot);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    auditQuery(tenantId, "kpi", "FAILURE", req);
    res.status(500).json({
      error: message,
      code: "KPI_SNAPSHOT_FAILED",
    });
  }
});

// ─── GET /api/analytics/revenue/locations ────────────────────────────────────

/**
 * Revenue breakdown by DSO location.
 *
 * Query params:
 *   startDate  ISO date string  (optional)
 *   endDate    ISO date string  (optional)
 *
 * Returns: RevenueByLocation[]
 *
 * Example:
 *   curl -H "X-Tenant-ID: <tenantId>" \
 *     "/api/analytics/revenue/locations?startDate=2025-01-01&endDate=2025-06-30"
 */
analyticsRouter.get(
  "/revenue/locations",
  async (req: Request, res: Response) => {
    const tenantId = requireTenantId(req, res);
    if (!tenantId) return;

    analyticsHeaders(res);

    const startDate = req.query.startDate
      ? new Date(req.query.startDate as string)
      : undefined;
    const endDate = req.query.endDate
      ? new Date(req.query.endDate as string)
      : undefined;

    if (startDate && isNaN(startDate.getTime())) {
      return res.status(400).json({
        error: "Invalid startDate — expected ISO date string",
        code: "INVALID_START_DATE",
      });
    }
    if (endDate && isNaN(endDate.getTime())) {
      return res.status(400).json({
        error: "Invalid endDate — expected ISO date string",
        code: "INVALID_END_DATE",
      });
    }

    try {
      const data = await AnalyticsService.getRevenueByLocation(
        tenantId,
        startDate,
        endDate
      );
      auditQuery(tenantId, "revenue/locations", "SUCCESS", req);
      res.json(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      auditQuery(tenantId, "revenue/locations", "FAILURE", req);
      res.status(500).json({
        error: message,
        code: "REVENUE_BY_LOCATION_FAILED",
      });
    }
  }
);

// ─── GET /api/analytics/funnel ────────────────────────────────────────────────

/**
 * Patient conversion funnel across all pipeline stages.
 *
 * Returns: ConversionFunnel[]
 *
 * Example:
 *   curl -H "X-Tenant-ID: <tenantId>" /api/analytics/funnel
 */
analyticsRouter.get("/funnel", async (req: Request, res: Response) => {
  const tenantId = requireTenantId(req, res);
  if (!tenantId) return;

  analyticsHeaders(res);

  try {
    const funnel = await AnalyticsService.getConversionFunnel(tenantId);
    auditQuery(tenantId, "funnel", "SUCCESS", req);
    res.json(funnel);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    auditQuery(tenantId, "funnel", "FAILURE", req);
    res.status(500).json({
      error: message,
      code: "CONVERSION_FUNNEL_FAILED",
    });
  }
});

// ─── GET /api/analytics/implants/trends ──────────────────────────────────────

/**
 * Monthly implant volume and revenue trends.
 *
 * Query params:
 *   months  number  How many trailing months to return (default 12, max 60)
 *
 * Returns: { month: string, count: number, revenue: number }[]
 *
 * Example:
 *   curl -H "X-Tenant-ID: <tenantId>" /api/analytics/implants/trends?months=6
 */
analyticsRouter.get(
  "/implants/trends",
  async (req: Request, res: Response) => {
    const tenantId = requireTenantId(req, res);
    if (!tenantId) return;

    analyticsHeaders(res);

    const rawMonths = req.query.months;
    let months = 12;
    if (rawMonths !== undefined) {
      months = parseInt(rawMonths as string, 10);
      if (isNaN(months) || months < 1 || months > 60) {
        return res.status(400).json({
          error: "months must be an integer between 1 and 60",
          code: "INVALID_MONTHS_PARAM",
        });
      }
    }

    try {
      const trends = await AnalyticsService.getImplantTrends(tenantId, months);
      auditQuery(tenantId, "implants/trends", "SUCCESS", req);
      res.json(trends);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      auditQuery(tenantId, "implants/trends", "FAILURE", req);
      res.status(500).json({
        error: message,
        code: "IMPLANT_TRENDS_FAILED",
      });
    }
  }
);

// ─── GET /api/analytics/acceptance/coordinator ───────────────────────────────

/**
 * Case acceptance rates by treatment coordinator.
 *
 * Returns: { coordinatorId: string, acceptanceRate: number, avgDaysToAccept: number }[]
 *
 * Example:
 *   curl -H "X-Tenant-ID: <tenantId>" /api/analytics/acceptance/coordinator
 */
analyticsRouter.get(
  "/acceptance/coordinator",
  async (req: Request, res: Response) => {
    const tenantId = requireTenantId(req, res);
    if (!tenantId) return;

    analyticsHeaders(res);

    try {
      const data =
        await AnalyticsService.getCaseAcceptanceByCoordinator(tenantId);
      auditQuery(tenantId, "acceptance/coordinator", "SUCCESS", req);
      res.json(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      auditQuery(tenantId, "acceptance/coordinator", "FAILURE", req);
      res.status(500).json({
        error: message,
        code: "COORDINATOR_ACCEPTANCE_FAILED",
      });
    }
  }
);

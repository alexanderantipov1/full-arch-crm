/**
 * full-arch-crm — Orchestration Routes
 * ──────────────────────────────────────
 * Exposes a single endpoint for triggering the nightly agent orchestration
 * loop on demand (e.g. for testing, debugging, or ad-hoc reporting).
 *
 * Routes:
 *   POST /api/orchestration/run
 *     Headers:
 *       X-Tenant-ID   — target tenant (required)
 *       X-Admin-Key   — admin secret matching ADMIN_API_KEY env var (required)
 *     Response:
 *       200  OrchestratorReport JSON
 *       400  Missing X-Tenant-ID
 *       401  Missing or invalid X-Admin-Key
 *       500  Orchestration error (message in body)
 *
 * Security:
 *   This endpoint bypasses the normal session-based auth and is secured
 *   instead with a static ADMIN_API_KEY secret — suitable for cron callers,
 *   CI pipelines, and internal tooling that cannot carry a session cookie.
 *   Set ADMIN_API_KEY in your environment variables.
 */

import { Router, type Request, type Response } from "express";
import { runOrchestrator, buildSlackBriefing } from "./orchestrator";

export const orchestrationRouter = Router();

// ─── Admin key guard ──────────────────────────────────────────────────────────

function requireAdminKey(req: Request, res: Response): boolean {
  const adminKey = process.env.ADMIN_API_KEY;
  const provided = req.headers["x-admin-key"];

  if (!adminKey) {
    // No key configured — block all access to prevent accidental open access
    res.status(500).json({
      message: "Server misconfiguration: ADMIN_API_KEY is not set",
    });
    return false;
  }

  if (!provided || provided !== adminKey) {
    res.status(401).json({ message: "Unauthorized: invalid or missing X-Admin-Key" });
    return false;
  }

  return true;
}

// ─── POST /api/orchestration/run ─────────────────────────────────────────────

/**
 * Manually trigger a full orchestration run for the given tenant.
 *
 * This is intentionally synchronous — it awaits the full run before returning
 * so callers get the complete OrchestratorReport in one shot.
 *
 * For production nightly runs use a cron trigger (e.g. node-cron or an
 * external scheduler) that calls this endpoint at 23:00 PDT each day.
 */
orchestrationRouter.post("/run", async (req: Request, res: Response) => {
  if (!requireAdminKey(req, res)) return;

  const tenantId = (req.headers["x-tenant-id"] as string | undefined)?.trim();
  if (!tenantId) {
    res.status(400).json({ message: "Missing required header: X-Tenant-ID" });
    return;
  }

  try {
    const report = await runOrchestrator(tenantId);
    const slackMessage = buildSlackBriefing(report);

    res.status(200).json({
      ...report,
      // Include the pre-formatted Slack message as a convenience field so
      // callers can post it directly without formatting it themselves.
      slackMessage,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown orchestration error";
    console.error("[orchestration-routes] runOrchestrator failed:", err);
    res.status(500).json({ message });
  }
});

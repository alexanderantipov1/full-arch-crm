import type { Request, Response, NextFunction } from "express";

// Admin gate for operator-only endpoints (MCP key management, future
// settings/audit-export tools, etc.). Today admin = `OWNER_USER_ID` plus
// any comma-separated entries in `ADMIN_USER_IDS`. Real role-based admin
// lands when the actor schema gets a `role` column.
//
// Mounts AFTER `isAuthenticated` — assumes `req.user.claims.sub` is set.
//
// The admin set is recomputed on every check (cheap — two env reads and
// a string split) instead of at module load. That keeps tests honest and
// lets operators rotate the set without redeploying.

function computeAdminSet(): Set<string> {
  const set = new Set<string>();
  const owner = process.env.OWNER_USER_ID;
  if (owner) set.add(owner);
  for (const id of (process.env.ADMIN_USER_IDS ?? "").split(",")) {
    const trimmed = id.trim();
    if (trimmed) set.add(trimmed);
  }
  return set;
}

export function isAdmin(req: Request, res: Response, next: NextFunction) {
  const userId = (req.user as any)?.claims?.sub ?? (req.user as any)?.id;
  if (!userId) return res.status(401).json({ message: "Unauthorized" });
  if (!computeAdminSet().has(userId)) {
    return res.status(403).json({ message: "Admin access required" });
  }
  next();
}

export function isAdminUserId(userId: string): boolean {
  return computeAdminSet().has(userId);
}

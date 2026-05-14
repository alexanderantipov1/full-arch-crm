import rateLimit, { ipKeyGenerator, type Options } from "express-rate-limit";
import type { Request } from "express";

const isProd = process.env.NODE_ENV === "production";

// Use the authenticated user id when available, otherwise fall back to the
// proxy-safe IP key. This means logged-in users get a per-account budget that
// can't be cleared by rotating IPs, while anonymous traffic is still limited.
function userOrIpKey(req: Request, res: any): string {
  const userId = (req as any).user?.claims?.sub || (req as any).user?.id;
  if (userId) return `u:${userId}`;
  return `ip:${ipKeyGenerator(req.ip ?? "")}`;
}

const baseOptions: Partial<Options> = {
  standardHeaders: "draft-7",
  legacyHeaders: false,
};

// Catch-all guard against runaway traffic on any API route. Generous limit so
// it only kicks in on abuse, not normal use of dashboards that fan out queries.
export const generalApiLimiter = rateLimit({
  ...baseOptions,
  windowMs: 60 * 1000,
  limit: isProd ? 300 : 1000,
  keyGenerator: userOrIpKey,
  message: { message: "Too many requests — slow down and try again shortly." },
});

// Login/callback are unauthenticated and brute-forceable. Always key by IP.
export const authLimiter = rateLimit({
  ...baseOptions,
  windowMs: 60 * 1000,
  limit: isProd ? 10 : 100,
  keyGenerator: (req) => `ip:${ipKeyGenerator(req.ip ?? "")}`,
  message: { message: "Too many login attempts — wait a minute before retrying." },
});

// AI endpoints are the expensive ones (per-call $ to Anthropic). Key by user
// so a single account can't drain the budget even from many IPs.
export const aiLimiter = rateLimit({
  ...baseOptions,
  windowMs: 60 * 1000,
  limit: isProd ? 30 : 200,
  keyGenerator: userOrIpKey,
  message: { message: "AI request limit reached — please wait a moment." },
});

// Payment creation: not as expensive as AI but we don't want to let one account
// spam Stripe with intents.
export const paymentLimiter = rateLimit({
  ...baseOptions,
  windowMs: 60 * 1000,
  limit: isProd ? 60 : 200,
  keyGenerator: userOrIpKey,
  message: { message: "Too many payment requests — please wait." },
});

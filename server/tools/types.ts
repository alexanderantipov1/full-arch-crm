import type { ZodSchema, ZodError } from "zod";

// The fusion_crm doctrine: tools take a `ToolContext` (principal + session)
// and delegate to services. Tools NEVER touch repositories or sessions
// directly. This file defines the shape we use to encode that contract.
//
// Migration goal: every AI-callable operation in full-arch-crm eventually
// becomes a Tool. AI agents will only see tools — never raw routes, never
// storage. For now we apply this incrementally as we touch each surface.

// ── Principal ────────────────────────────────────────────────────────────
// Whoever is calling the tool. Today this is a logged-in staff user, an
// authenticated MCP client, or a test fixture. Later: AI agents (with their
// own actor row) and patient portal users (different subject type entirely).
//
// Capabilities follow a deny-by-default model: a principal constructed
// without an explicit capability set has NO access to PHI. The HIPAA
// posture this enforces — you can't accidentally call PhiService from a
// context that didn't deliberately opt into PHI access.

export type Capability =
  | "phi.read"   // read patient profile, medical history, clinical data
  | "phi.write"; // create/update PHI records

export interface Principal {
  userId: string;
  email?: string;
  capabilities?: Set<Capability>;
}

export function hasCapability(p: Principal, cap: Capability): boolean {
  return p.capabilities?.has(cap) ?? false;
}

// Factory that builds a Principal with an explicit capability list. Pass an
// empty array to model an unprivileged caller (useful for tests + future
// agent capability scoping).
export function makePrincipal(opts: {
  userId: string;
  email?: string;
  capabilities?: Capability[];
}): Principal {
  return {
    userId: opts.userId,
    email: opts.email,
    capabilities: new Set(opts.capabilities ?? []),
  };
}

// ── ToolContext ──────────────────────────────────────────────────────────
// Carried by every tool invocation. Keep this small — anything that grows
// beyond identity (e.g. tenant id, request id) gets its own field.

export interface ToolContext {
  principal: Principal;
  requestId?: string;
}

// ── Result ──────────────────────────────────────────────────────────────
// Discriminated union so callers must check `.ok` before using `.data`.
// The error shape mirrors the fusion_crm envelope: `{ code, message, details? }`.

export type ToolResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: ToolError };

export interface ToolError {
  code: string;
  message: string;
  details?: unknown;
}

// ── Tool definition ─────────────────────────────────────────────────────
// `defineTool` is the constructor. Tools are plain values, so they're easy
// to test in isolation and easy to enumerate for an MCP-style listing later.

export interface Tool<Input, Output> {
  name: string;
  description: string;
  inputSchema: ZodSchema<Input>;
  handler: (ctx: ToolContext, input: Input) => Promise<ToolResult<Output>>;
}

export function defineTool<Input, Output>(
  spec: Tool<Input, Output>,
): Tool<Input, Output> {
  return spec;
}

// ── Conventional error codes ────────────────────────────────────────────
// Tools should use these where they fit so the HTTP layer's status mapping
// stays consistent. Unrecognized codes default to 500.

export const ToolErrorCode = {
  ValidationFailed: "validation.failed",
  NotFound: "not_found",
  Unauthorized: "auth.unauthorized",
  Forbidden: "auth.forbidden",
  Conflict: "conflict",
  AiResponseInvalid: "ai.invalid_response",
  AiCallFailed: "ai.call_failed",
  // PHI access denied by the PhiService capability check. Separate from
  // generic Forbidden so callers can distinguish "you can't do this at all"
  // from "you can't read patient health data specifically".
  PhiAccessDenied: "phi.access_denied",
  Internal: "internal",
} as const;

// Helper used by tools that want to surface a Zod validation failure.
export function zodErrorToToolError(error: ZodError): ToolError {
  return {
    code: ToolErrorCode.ValidationFailed,
    message: error.errors[0]?.message ?? "Validation failed",
    details: { issues: error.errors },
  };
}

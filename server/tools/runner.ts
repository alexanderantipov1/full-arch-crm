import type { Request, Response } from "express";
import {
  type Principal,
  type Tool,
  type ToolContext,
  type ToolError,
  type ToolResult,
  ToolErrorCode,
  makePrincipal,
  zodErrorToToolError,
} from "./types";

// ── Adapter from Express req → Principal ─────────────────────────────────
// Today the only principal source is the OIDC session (`req.user.claims`).
// All staff get the full capability set; per-role scoping lands when we
// introduce real role tables. When AI agents and portal users get their
// own auth, this is where the principal-type dispatch will live (and they
// get DIFFERENT capability sets — patient portal users can read only their
// own PHI, marketing AI agents get no PHI at all, etc.).

export function principalFromReq(req: Request): Principal {
  const user = req.user as any;
  const userId = user?.claims?.sub ?? user?.id ?? "unknown";
  const email = user?.claims?.email ?? user?.email;
  return makePrincipal({
    userId,
    email,
    capabilities: ["phi.read", "phi.write"],
  });
}

// ── HTTP status mapping ──────────────────────────────────────────────────
// Tool error codes are semantic; the HTTP layer translates to status codes.
// Anything unknown defaults to 500 so we never leak a 200 + error envelope.

export function httpStatusForToolError(code: string): number {
  switch (code) {
    case ToolErrorCode.ValidationFailed:
      return 400;
    case ToolErrorCode.Unauthorized:
      return 401;
    case ToolErrorCode.Forbidden:
    case ToolErrorCode.PhiAccessDenied:
      return 403;
    case ToolErrorCode.NotFound:
      return 404;
    case ToolErrorCode.Conflict:
      return 409;
    case ToolErrorCode.AiResponseInvalid:
    case ToolErrorCode.AiCallFailed:
      return 502;
    default:
      return 500;
  }
}

// ── runTool ──────────────────────────────────────────────────────────────
// Single entry point used by route handlers. Validates input with the tool's
// Zod schema, calls the handler, returns a `ToolResult`. Route handlers
// never call `tool.handler(...)` directly — they go through this so
// validation and error shaping happens in one place.

export async function runTool<I, O>(
  tool: Tool<I, O>,
  ctx: ToolContext,
  rawInput: unknown,
): Promise<ToolResult<O>> {
  const parsed = tool.inputSchema.safeParse(rawInput);
  if (!parsed.success) {
    return { ok: false, error: zodErrorToToolError(parsed.error) };
  }
  try {
    return await tool.handler(ctx, parsed.data);
  } catch (err: any) {
    // Unhandled exceptions inside a tool — log and surface as internal so
    // we don't leak driver/stack details to the caller.
    console.error(`Tool '${tool.name}' threw:`, err);
    return {
      ok: false,
      error: { code: ToolErrorCode.Internal, message: "Tool execution failed" },
    };
  }
}

// ── mountTool ────────────────────────────────────────────────────────────
// Convenience for the common case: POST endpoint that takes JSON in,
// returns the tool's data shape out, maps tool errors to HTTP status codes.
// For endpoints with custom auth / extra middleware / non-JSON bodies, wire
// the tool by hand using `runTool` directly.

export function respondWithToolResult<T>(res: Response, result: ToolResult<T>) {
  if (result.ok) {
    return res.json(result.data);
  }
  const status = httpStatusForToolError(result.error.code);
  return res.status(status).json({ error: result.error });
}

export function toolErrorFromException(err: unknown): ToolError {
  if (err instanceof Error) {
    return { code: ToolErrorCode.Internal, message: err.message };
  }
  return { code: ToolErrorCode.Internal, message: "Unknown error" };
}

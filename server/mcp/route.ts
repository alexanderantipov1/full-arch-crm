import type { Express, Request, Response } from "express";
import { mcpAuth } from "./auth";
import { handleMcpRequest } from "./server";

// Mount the MCP HTTP transport at /mcp. Stateless JSON-RPC: one request →
// one response, no SSE. This is enough for tools/list + tools/call from a
// remote Claude Code client.
//
// Auth is a separate bearer-token middleware (mcpAuth) — staff OIDC cookies
// don't apply here because MCP clients are services, not browsers.

export function registerMcpRoutes(app: Express) {
  app.post("/mcp", mcpAuth, async (req: Request, res: Response) => {
    const principal = req.mcpPrincipal!;
    const response = await handleMcpRequest(req.body, principal);
    res.json(response);
  });
}

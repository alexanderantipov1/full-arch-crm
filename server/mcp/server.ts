import { zodToJsonSchema } from "zod-to-json-schema";
import { listTools, getToolByName } from "../tools/registry";
import { runTool } from "../tools/runner";
import type { Principal, ToolResult } from "../tools/types";

// Minimal JSON-RPC 2.0 dispatcher implementing the MCP methods we need for
// stateless HTTP transport:
//
//   - initialize        → handshake; returns protocol + server info
//   - tools/list        → enumerate available tools with JSON schemas
//   - tools/call        → invoke a named tool with arguments
//
// This is NOT a full MCP implementation — it intentionally omits resources,
// prompts, completion, SSE notifications. Those land if/when a client needs
// them. The wire format matches MCP spec so a real MCP client (Claude Code
// over HTTP) can connect and call tools.

const PROTOCOL_VERSION = "2024-11-05";
const SERVER_NAME = "fusion-crm";
const SERVER_VERSION = "0.1.0";

interface JsonRpcRequest {
  jsonrpc: "2.0";
  id?: string | number | null;
  method: string;
  params?: Record<string, unknown>;
}

interface JsonRpcSuccess<T> {
  jsonrpc: "2.0";
  id: string | number | null;
  result: T;
}

interface JsonRpcFailure {
  jsonrpc: "2.0";
  id: string | number | null;
  error: { code: number; message: string; data?: unknown };
}

// Standard JSON-RPC error codes (kept here so the rest of the file reads
// without magic numbers).
const JsonRpcError = {
  ParseError: -32700,
  InvalidRequest: -32600,
  MethodNotFound: -32601,
  InvalidParams: -32602,
  InternalError: -32603,
} as const;

function ok<T>(id: JsonRpcRequest["id"], result: T): JsonRpcSuccess<T> {
  return { jsonrpc: "2.0", id: id ?? null, result };
}

function fail(
  id: JsonRpcRequest["id"],
  code: number,
  message: string,
  data?: unknown,
): JsonRpcFailure {
  return { jsonrpc: "2.0", id: id ?? null, error: { code, message, data } };
}

// MCP `tools/list` response shape — each tool has a JSON Schema for its input.
function toolToMcpDescriptor(tool: ReturnType<typeof listTools>[number]) {
  return {
    name: tool.name,
    description: tool.description,
    inputSchema: zodToJsonSchema(tool.inputSchema, { target: "openApi3" }),
  };
}

export async function handleMcpRequest(
  body: unknown,
  principal: Principal,
): Promise<JsonRpcSuccess<unknown> | JsonRpcFailure> {
  if (!body || typeof body !== "object" || (body as any).jsonrpc !== "2.0") {
    return fail(null, JsonRpcError.InvalidRequest, "Invalid JSON-RPC envelope");
  }

  const req = body as JsonRpcRequest;
  const id = req.id ?? null;

  switch (req.method) {
    case "initialize":
      return ok(id, {
        protocolVersion: PROTOCOL_VERSION,
        serverInfo: { name: SERVER_NAME, version: SERVER_VERSION },
        capabilities: { tools: {} },
      });

    case "tools/list":
      return ok(id, {
        tools: listTools().map(toolToMcpDescriptor),
      });

    case "tools/call": {
      const params = req.params ?? {};
      const name = typeof params.name === "string" ? params.name : null;
      const args = (params.arguments as Record<string, unknown> | undefined) ?? {};
      if (!name) {
        return fail(id, JsonRpcError.InvalidParams, "Missing 'name' parameter");
      }

      const tool = getToolByName(name);
      if (!tool) {
        return fail(id, JsonRpcError.MethodNotFound, `Unknown tool: ${name}`);
      }

      const result: ToolResult<unknown> = await runTool(tool, { principal }, args);
      if (!result.ok) {
        // Tool errors get reported as MCP `isError: true` content rather than
        // JSON-RPC errors — MCP convention is that the protocol succeeded but
        // the tool itself failed. Clients can still see the structured error.
        return ok(id, {
          isError: true,
          content: [
            { type: "text", text: result.error.message },
          ],
          _meta: { error: result.error },
        });
      }

      return ok(id, {
        content: [
          { type: "text", text: JSON.stringify(result.data, null, 2) },
        ],
        structuredContent: result.data,
      });
    }

    default:
      return fail(id, JsonRpcError.MethodNotFound, `Unknown method: ${req.method}`);
  }
}

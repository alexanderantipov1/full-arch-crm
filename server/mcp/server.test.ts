import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the AI service so tools/call never hits Anthropic.
vi.mock("../services/ai", () => ({
  askClaude: vi.fn().mockResolvedValue('{"suggestedCDT":[{"code":"D6010","description":"Implant"}]}'),
  anthropic: { messages: { create: vi.fn() } },
}));

import { handleMcpRequest } from "./server";

const principal = { userId: "mcp:default", email: "mcp@test" };

beforeEach(() => vi.clearAllMocks());

describe("MCP JSON-RPC dispatcher", () => {
  describe("initialize", () => {
    it("returns protocol version + server info + tools capability", async () => {
      const res = await handleMcpRequest(
        { jsonrpc: "2.0", id: 1, method: "initialize" },
        principal,
      );
      expect("result" in res).toBe(true);
      if ("result" in res) {
        const result = res.result as any;
        expect(result.protocolVersion).toBe("2024-11-05");
        expect(result.serverInfo.name).toBe("fusion-crm");
        expect(result.capabilities.tools).toBeDefined();
      }
    });
  });

  describe("tools/list", () => {
    it("returns the full tool catalog with JSON schemas", async () => {
      const res = await handleMcpRequest(
        { jsonrpc: "2.0", id: 2, method: "tools/list" },
        principal,
      );
      expect("result" in res).toBe(true);
      if (!("result" in res)) return;
      const result = res.result as any;
      const names = result.tools.map((t: any) => t.name);
      expect(names).toContain("coding.suggestCodes");
      expect(names).toContain("ai.chat");
      expect(names).toContain("documents.generate");
      // Each tool has a name, description, and inputSchema.
      for (const tool of result.tools) {
        expect(tool.name).toBeTruthy();
        expect(tool.description).toBeTruthy();
        expect(tool.inputSchema).toBeDefined();
      }
    });
  });

  describe("tools/call", () => {
    it("dispatches to the named tool and returns structured content", async () => {
      const res = await handleMcpRequest(
        {
          jsonrpc: "2.0",
          id: 3,
          method: "tools/call",
          params: {
            name: "coding.suggestCodes",
            arguments: {
              diagnosis: "edentulism",
              procedures: "full-arch upper implant",
            },
          },
        },
        principal,
      );
      expect("result" in res).toBe(true);
      if (!("result" in res)) return;
      const result = res.result as any;
      expect(result.isError).toBeUndefined();
      expect(result.structuredContent.suggestedCDT[0].code).toBe("D6010");
      expect(result.content[0].type).toBe("text");
    });

    it("returns isError:true when the tool fails validation (still a JSON-RPC success)", async () => {
      const res = await handleMcpRequest(
        {
          jsonrpc: "2.0",
          id: 4,
          method: "tools/call",
          params: {
            name: "coding.suggestCodes",
            arguments: { diagnosis: "", procedures: "" },
          },
        },
        principal,
      );
      // Tool errors are NOT JSON-RPC errors — protocol succeeded.
      expect("result" in res).toBe(true);
      if (!("result" in res)) return;
      const result = res.result as any;
      expect(result.isError).toBe(true);
      expect(result._meta.error.code).toBe("validation.failed");
    });

    it("returns JSON-RPC -32601 for unknown tool name", async () => {
      const res = await handleMcpRequest(
        {
          jsonrpc: "2.0",
          id: 5,
          method: "tools/call",
          params: { name: "no.such.tool", arguments: {} },
        },
        principal,
      );
      expect("error" in res).toBe(true);
      if ("error" in res) {
        expect(res.error.code).toBe(-32601);
        expect(res.error.message).toMatch(/Unknown tool/);
      }
    });

    it("returns JSON-RPC -32602 when 'name' is missing", async () => {
      const res = await handleMcpRequest(
        { jsonrpc: "2.0", id: 6, method: "tools/call", params: {} },
        principal,
      );
      expect("error" in res).toBe(true);
      if ("error" in res) expect(res.error.code).toBe(-32602);
    });
  });

  describe("unknown method", () => {
    it("returns JSON-RPC -32601", async () => {
      const res = await handleMcpRequest(
        { jsonrpc: "2.0", id: 7, method: "no/such/method" },
        principal,
      );
      expect("error" in res).toBe(true);
      if ("error" in res) expect(res.error.code).toBe(-32601);
    });
  });

  describe("malformed envelope", () => {
    it("returns JSON-RPC -32600 for non-2.0 jsonrpc field", async () => {
      const res = await handleMcpRequest(
        { jsonrpc: "1.0", method: "tools/list" } as any,
        principal,
      );
      expect("error" in res).toBe(true);
      if ("error" in res) expect(res.error.code).toBe(-32600);
    });
  });
});

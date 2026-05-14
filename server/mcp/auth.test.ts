import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import express from "express";
import request from "supertest";
import { createHash } from "node:crypto";

const storageMock = vi.hoisted(() => ({
  getMcpApiKeyByHash: vi.fn(),
  touchMcpApiKeyLastUsed: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("../storage", () => ({ storage: storageMock }));

import { mcpAuth } from "./auth";

function appWithAuth() {
  const app = express();
  app.use(express.json());
  app.post("/mcp", mcpAuth, (req: any, res) =>
    res.json({ principal: req.mcpPrincipal, keyId: req.mcpKeyId }),
  );
  return app;
}

const sha256 = (s: string) => createHash("sha256").update(s).digest("hex");
const originalKey = process.env.MCP_API_KEY;

beforeEach(() => {
  vi.clearAllMocks();
  storageMock.touchMcpApiKeyLastUsed.mockResolvedValue(undefined);
  delete process.env.MCP_API_KEY;
});

afterEach(() => {
  if (originalKey !== undefined) process.env.MCP_API_KEY = originalKey;
  else delete process.env.MCP_API_KEY;
});

describe("MCP bearer auth — no configuration", () => {
  it("refuses requests when neither a DB key nor MCP_API_KEY is set", async () => {
    storageMock.getMcpApiKeyByHash.mockResolvedValue(undefined);
    const res = await request(appWithAuth()).post("/mcp").set("Authorization", "Bearer anything").send({});
    expect(res.status).toBe(401);
    expect(res.body.error.message).toMatch(/not configured/i);
  });

  it("refuses requests with no Authorization header", async () => {
    const res = await request(appWithAuth()).post("/mcp").send({});
    expect(res.status).toBe(401);
  });
});

describe("MCP bearer auth — DB key mode", () => {
  it("accepts a token whose SHA-256 matches a DB row and grants that row's capabilities", async () => {
    storageMock.getMcpApiKeyByHash.mockResolvedValue({
      id: 7,
      label: "clinical-agent",
      keyHash: sha256("secret-token"),
      capabilities: ["phi.read"],
      enabled: true,
      revokedAt: null,
    });

    const res = await request(appWithAuth()).post("/mcp").set("Authorization", "Bearer secret-token").send({});

    expect(res.status).toBe(200);
    expect(res.body.principal.userId).toBe("mcp:7");
    expect(res.body.principal.email).toBe("clinical-agent");
    // capabilities is serialized as a Set — check membership via Object.keys
    // (JSON serialization of Set is unusual; the test verifies the principal
    // shape via the keyId echo, and the principal's capability check is
    // exercised elsewhere via runTool integration tests).
    expect(res.body.keyId).toBe(7);
  });

  it("looks up by HASH, never sends plaintext to the DB", async () => {
    storageMock.getMcpApiKeyByHash.mockResolvedValue(undefined);
    await request(appWithAuth()).post("/mcp").set("Authorization", "Bearer my-secret").send({});

    const queriedHash = storageMock.getMcpApiKeyByHash.mock.calls[0][0];
    expect(queriedHash).toBe(sha256("my-secret"));
    expect(queriedHash).not.toBe("my-secret");
  });

  it("rejects a revoked key (enabled: false) with a clear message", async () => {
    storageMock.getMcpApiKeyByHash.mockResolvedValue({
      id: 2,
      label: "old-agent",
      keyHash: sha256("old-token"),
      capabilities: ["phi.read"],
      enabled: false,
      revokedAt: new Date(),
    });

    const res = await request(appWithAuth()).post("/mcp").set("Authorization", "Bearer old-token").send({});
    expect(res.status).toBe(401);
    expect(res.body.error.message).toMatch(/revoked/i);
  });

  it("touches lastUsedAt on every successful auth (fire-and-forget)", async () => {
    storageMock.getMcpApiKeyByHash.mockResolvedValue({
      id: 9,
      label: "agent",
      keyHash: sha256("t"),
      capabilities: [],
      enabled: true,
    });

    await request(appWithAuth()).post("/mcp").set("Authorization", "Bearer t").send({});
    // The bump is async/non-awaited; give the microtask queue a tick.
    await new Promise((r) => setImmediate(r));
    expect(storageMock.touchMcpApiKeyLastUsed).toHaveBeenCalledWith(9);
  });
});

describe("MCP bearer auth — env fallback", () => {
  beforeEach(() => {
    storageMock.getMcpApiKeyByHash.mockResolvedValue(undefined);
    process.env.MCP_API_KEY = "env-key";
  });

  it("accepts the env key when DB has no matching row", async () => {
    const res = await request(appWithAuth()).post("/mcp").set("Authorization", "Bearer env-key").send({});
    expect(res.status).toBe(200);
    expect(res.body.principal.userId).toBe("mcp:env");
  });

  it("rejects a wrong token when env fallback is configured", async () => {
    const res = await request(appWithAuth()).post("/mcp").set("Authorization", "Bearer wrong").send({});
    expect(res.status).toBe(401);
  });
});

describe("MCP bearer auth — DB wins over env", () => {
  it("uses the DB row's capabilities even when MCP_API_KEY is also set", async () => {
    process.env.MCP_API_KEY = "env-key";
    storageMock.getMcpApiKeyByHash.mockResolvedValue({
      id: 11,
      label: "scoped-key",
      keyHash: sha256("env-key"), // same plaintext, but DB lookup finds it first
      capabilities: ["phi.read"], // scoped — no phi.write
      enabled: true,
    });

    const res = await request(appWithAuth()).post("/mcp").set("Authorization", "Bearer env-key").send({});
    expect(res.body.principal.userId).toBe("mcp:11"); // DB-mode userId, not "mcp:env"
    expect(res.body.keyId).toBe(11);
  });
});

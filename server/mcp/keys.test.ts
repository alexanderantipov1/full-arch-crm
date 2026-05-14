import { describe, it, expect, vi, beforeEach } from "vitest";

const storageMock = vi.hoisted(() => ({
  createMcpApiKey: vi.fn(),
  listMcpApiKeys: vi.fn(),
}));
vi.mock("../storage", () => ({ storage: storageMock }));

import { generateMcpApiKey, sanitizeMcpApiKey, sha256Hex } from "./keys";

beforeEach(() => vi.clearAllMocks());

describe("generateMcpApiKey", () => {
  it("rejects empty labels", async () => {
    await expect(generateMcpApiKey({ label: "", capabilities: [] })).rejects.toThrow(/label/);
    await expect(generateMcpApiKey({ label: "   ", capabilities: [] })).rejects.toThrow(/label/);
  });

  it("mints a prefixed token, hashes it before storing, and returns plaintext exactly once", async () => {
    storageMock.createMcpApiKey.mockImplementation(async (data: any) => ({ id: 7, ...data }));

    const created = await generateMcpApiKey({
      label: "test-key",
      capabilities: ["phi.read"] as any,
      createdBy: "admin-1",
    });

    // Token shape: `mcp_<64-hex>`.
    expect(created.token).toMatch(/^mcp_[0-9a-f]{64}$/);
    expect(created.id).toBe(7);

    // The DB row was written with the HASH, not the plaintext.
    const args = storageMock.createMcpApiKey.mock.calls[0][0];
    expect(args.keyHash).toBe(sha256Hex(created.token));
    expect(args.keyHash).not.toBe(created.token);
    expect(args.label).toBe("test-key");
    expect(args.capabilities).toEqual(["phi.read"]);
    expect(args.enabled).toBe(true);
    expect(args.createdBy).toBe("admin-1");
  });

  it("generates distinct tokens on successive calls", async () => {
    storageMock.createMcpApiKey.mockImplementation(async (data: any) => ({ id: 1, ...data }));
    const a = await generateMcpApiKey({ label: "a", capabilities: [] });
    const b = await generateMcpApiKey({ label: "b", capabilities: [] });
    expect(a.token).not.toBe(b.token);
  });
});

describe("sanitizeMcpApiKey", () => {
  it("strips the keyHash field but keeps the rest", () => {
    const row = {
      id: 1,
      label: "k",
      keyHash: "abc123",
      capabilities: ["phi.read"],
      enabled: true,
      createdBy: "x",
      lastUsedAt: null,
      createdAt: new Date(),
      revokedAt: null,
    };
    const sanitized = sanitizeMcpApiKey(row as any);
    expect(sanitized).not.toHaveProperty("keyHash");
    expect(sanitized).toMatchObject({ id: 1, label: "k", enabled: true });
  });
});

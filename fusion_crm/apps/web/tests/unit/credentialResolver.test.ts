/**
 * ENG-125 — credential resolver fallback ordering.
 *
 * Asserts the DB-first / env-fallback contract: the resolver hits the
 * FastAPI ``/_internal/credentials/...`` endpoint first; on any
 * non-200 response (including the 503 not-configured signal) the
 * caller can fall back to ``process.env.*``.
 *
 * Test seam: ``_resetCredentialCacheForTests`` clears the in-memory
 * 60s cache between cases.
 */
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  _resetCredentialCacheForTests,
  resolveCredential,
} from "@/lib/credentials/resolver";

const TOKEN = "test-internal-token-DO-NOT-USE-IN-PROD";

beforeEach(() => {
  _resetCredentialCacheForTests();
  process.env.INTERNAL_CREDENTIAL_TOKEN = TOKEN;
  process.env.INTERNAL_API_BASE_URL = "http://localhost:8000";
});

afterEach(() => {
  vi.restoreAllMocks();
  delete process.env.INTERNAL_CREDENTIAL_TOKEN;
  delete process.env.INTERNAL_API_URL;
  delete process.env.INTERNAL_API_BASE_URL;
  delete process.env.K_SERVICE;
});

describe("resolveCredential — DB-first, env-fallback ordering", () => {
  it("returns the JSON body on a 200 response", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ access_token: "abc", instance_url: "https://x" }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );

    const out = await resolveCredential("salesforce", "oauth_token");
    expect(out).toEqual({ access_token: "abc", instance_url: "https://x" });

    expect(fetchSpy).toHaveBeenCalledOnce();
    const url = fetchSpy.mock.calls[0]![0] as string;
    expect(url).toContain("/_internal/credentials/salesforce/oauth_token");
    const init = fetchSpy.mock.calls[0]![1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers["X-Internal-Token"]).toBe(TOKEN);
  });

  it("returns null on a 404 (no row) so the caller can env-fallback", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "no_credential" } }), {
        status: 404,
      }),
    );
    const out = await resolveCredential("salesforce", "oauth_token");
    expect(out).toBeNull();
  });

  it("returns null on a 503 not_configured", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response("", { status: 503 }),
    );
    const out = await resolveCredential("carestack", "password_grant");
    expect(out).toBeNull();
  });

  it("returns null on a network error", async () => {
    vi.spyOn(global, "fetch").mockRejectedValue(new TypeError("ECONNREFUSED"));
    const out = await resolveCredential("salesforce", "oauth_token");
    expect(out).toBeNull();
  });

  it("returns null when the internal token is unset (resolver disabled)", async () => {
    delete process.env.INTERNAL_CREDENTIAL_TOKEN;
    const fetchSpy = vi.spyOn(global, "fetch");
    const out = await resolveCredential("salesforce", "oauth_token");
    expect(out).toBeNull();
    // No HTTP call was made — the resolver short-circuited.
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("prefers INTERNAL_API_URL over INTERNAL_API_BASE_URL", async () => {
    process.env.INTERNAL_API_URL = "https://fusion-api.example.run.app";
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ access_token: "abc" }), { status: 200 }),
    );

    await resolveCredential("salesforce", "oauth_token");

    const url = fetchSpy.mock.calls[0]![0] as string;
    expect(url).toContain("https://fusion-api.example.run.app");
  });

  it("attaches a Cloud Run identity token when calling a run.app API URL", async () => {
    process.env.K_SERVICE = "fusion-web";
    process.env.INTERNAL_API_URL = "https://fusion-api.example.run.app";
    const fetchSpy = vi.spyOn(global, "fetch").mockImplementation((url) => {
      const u = String(url);
      if (u.startsWith("http://metadata.google.internal/")) {
        return Promise.resolve(new Response("identity-token", { status: 200 }));
      }
      return Promise.resolve(
        new Response(JSON.stringify({ access_token: "abc" }), { status: 200 }),
      );
    });

    await resolveCredential("salesforce", "oauth_token");

    expect(fetchSpy).toHaveBeenCalledTimes(2);
    const apiCall = fetchSpy.mock.calls[1]!;
    const init = apiCall[1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer identity-token");
  });

  it("caches the response so the second call does not refetch", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ access_token: "abc" }), { status: 200 }),
    );

    await resolveCredential("salesforce", "oauth_token");
    await resolveCredential("salesforce", "oauth_token");
    expect(fetchSpy).toHaveBeenCalledOnce();
  });

  it("does not cross-contaminate provider+kind cache keys", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockImplementation((url) => {
      const u = url as string;
      if (u.includes("salesforce/api_key")) {
        return Promise.resolve(
          new Response(JSON.stringify({ client_id: "sf" }), { status: 200 }),
        );
      }
      if (u.includes("carestack/password_grant")) {
        return Promise.resolve(
          new Response(JSON.stringify({ vendor_key: "cs" }), { status: 200 }),
        );
      }
      return Promise.resolve(new Response("", { status: 404 }));
    });

    const sf = await resolveCredential("salesforce", "api_key");
    const cs = await resolveCredential("carestack", "password_grant");
    expect(sf).toEqual({ client_id: "sf" });
    expect(cs).toEqual({ vendor_key: "cs" });
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });
});

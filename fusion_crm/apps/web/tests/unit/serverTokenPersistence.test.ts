import { beforeEach, describe, expect, it, vi } from "vitest";

const credentialMocks = vi.hoisted(() => ({
  resolveCredential: vi.fn(),
  persistCredential: vi.fn(),
}));

const sfTokenMocks = vi.hoisted(() => ({
  readTokens: vi.fn(),
  writeTokens: vi.fn(),
}));

const csTokenMocks = vi.hoisted(() => ({
  writeCSTokens: vi.fn(),
}));

vi.mock("@/lib/credentials/resolver", () => credentialMocks);

vi.mock("@/lib/sf/tokens", () => ({
  readTokens: sfTokenMocks.readTokens,
  writeTokens: sfTokenMocks.writeTokens,
}));

vi.mock("@/lib/cs/tokens", () => ({
  writeCSTokens: csTokenMocks.writeCSTokens,
}));

describe("server token persistence in read-only runtimes", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    credentialMocks.resolveCredential.mockReset();
    credentialMocks.persistCredential.mockReset();
    sfTokenMocks.readTokens.mockReset();
    sfTokenMocks.writeTokens.mockReset();
    csTokenMocks.writeCSTokens.mockReset();
  });

  it("refreshes Salesforce tokens when the dev token file is not writable", async () => {
    credentialMocks.resolveCredential.mockImplementation(
      async (provider: string, kind: string) => {
        if (provider === "salesforce" && kind === "api_key") {
          return {
            client_id: "client-id",
            client_secret: "client-secret",
            callback_url: "https://fusioncrm.app/api/integrations/salesforce/callback",
            domain: "login.salesforce.com",
          };
        }
        if (provider === "salesforce" && kind === "oauth_token") {
          return {
            access_token: "old-access",
            refresh_token: "refresh-token",
            instance_url: "https://example.my.salesforce.com",
            issued_at: "old-issued",
          };
        }
        return null;
      },
    );
    credentialMocks.persistCredential.mockResolvedValue(true);
    sfTokenMocks.writeTokens.mockRejectedValue(
      Object.assign(new Error("EACCES"), { code: "EACCES" }),
    );
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: "new-access",
          instance_url: "https://example.my.salesforce.com",
          issued_at: "new-issued",
          token_type: "Bearer",
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );

    const { refreshAccessToken } = await import("@/lib/sf/oauth");
    const out = await refreshAccessToken();

    expect(out.access_token).toBe("new-access");
    expect(out.refresh_token).toBe("refresh-token");
    expect(credentialMocks.persistCredential).toHaveBeenCalledWith(
      "salesforce",
      "oauth_token",
      expect.objectContaining({ access_token: "new-access" }),
    );
    expect(sfTokenMocks.writeTokens).toHaveBeenCalledOnce();
  });

  it("fetches a CareStack access token when the dev token file is not writable", async () => {
    credentialMocks.resolveCredential.mockImplementation(
      async (provider: string, kind: string) => {
        if (provider === "carestack" && kind === "password_grant") {
          return {
            client_id: "client-id",
            client_secret: "client-secret",
            vendor_key: "vendor-key",
            account_key: "account-key",
            account_id: "account-id",
            idp_base_url: "https://idp.example",
            api_base_url: "https://api.example",
            api_version: "v1.0",
          };
        }
        return null;
      },
    );
    csTokenMocks.writeCSTokens.mockRejectedValue(
      Object.assign(new Error("EACCES"), { code: "EACCES" }),
    );
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: "cs-access",
          token_type: "Bearer",
          expires_in: 7200,
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );

    const { fetchAccessToken } = await import("@/lib/cs/auth");
    const out = await fetchAccessToken();

    expect(out.access_token).toBe("cs-access");
    expect(out.account_id).toBe("account-id");
    expect(csTokenMocks.writeCSTokens).toHaveBeenCalledOnce();
  });
});

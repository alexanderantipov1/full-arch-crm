import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useUpsertBootstrapCredential } from "@/lib/api/hooks/useCredentials";

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("useUpsertBootstrapCredential", () => {
  it("posts secret-bearing input and parses metadata-only response", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body));
      expect(body.client_secret).toBe("sf-client-secret");
      return new Response(
        JSON.stringify({
          id: "ff000077-0000-0000-0000-000000000077",
          tenant_id: "11111111-1111-1111-1111-111111111111",
          provider_kind: "salesforce",
          credential_kind: "api_key",
          display_name: "Salesforce app",
          status: "active",
          expires_at: null,
          last_refreshed_at: null,
          mailbox_email: null,
          location_id: null,
          is_default: false,
          tags: [],
          created_at: "2026-01-01T00:00:00+00:00",
          updated_at: "2026-01-01T00:00:00+00:00",
          payload: { ciphertext: "must-strip" },
        }),
        { status: 200 },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useUpsertBootstrapCredential(), {
      wrapper,
    });

    result.current.mutate({
      provider_kind: "salesforce",
      credential_kind: "api_key",
      display_name: "Salesforce app",
      client_id: "sf-client-id",
      client_secret: "sf-client-secret",
      callback_url: "https://fusioncrm.app/api/integrations/salesforce/callback",
      domain: "login.salesforce.com",
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/tenant/credentials",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.current.data).toMatchObject({
      provider_kind: "salesforce",
      credential_kind: "api_key",
    });
    expect(JSON.stringify(result.current.data)).not.toContain(
      "sf-client-secret",
    );
    expect(JSON.stringify(result.current.data)).not.toContain("must-strip");
  });

  it("rejects unsupported bootstrap providers before posting", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useUpsertBootstrapCredential(), {
      wrapper,
    });

    await expect(
      result.current.mutateAsync({
        provider_kind: "hubspot",
        credential_kind: "api_key",
        display_name: "HubSpot app",
        client_id: "hubspot-client-id",
        client_secret: "hubspot-client-secret",
      } as never),
    ).rejects.toThrow();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("accepts OpenAI API-key bootstrap input", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body));
      expect(body.provider_kind).toBe("openai");
      expect(body.api_key).toBe("sk-test-openai-secret");
      return new Response(
        JSON.stringify({
          id: "ff000077-0000-0000-0000-000000000077",
          tenant_id: "11111111-1111-1111-1111-111111111111",
          provider_kind: "openai",
          credential_kind: "api_key",
          display_name: "OpenAI primary",
          status: "active",
          expires_at: null,
          last_refreshed_at: null,
          mailbox_email: null,
          location_id: null,
          is_default: true,
          tags: [],
          created_at: "2026-01-01T00:00:00+00:00",
          updated_at: "2026-01-01T00:00:00+00:00",
        }),
        { status: 200 },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useUpsertBootstrapCredential(), {
      wrapper,
    });

    result.current.mutate({
      provider_kind: "openai",
      credential_kind: "api_key",
      display_name: "OpenAI primary",
      api_key: "sk-test-openai-secret",
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toMatchObject({
      provider_kind: "openai",
      credential_kind: "api_key",
    });
  });
});

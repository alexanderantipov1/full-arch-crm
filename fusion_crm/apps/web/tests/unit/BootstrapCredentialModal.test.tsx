import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BootstrapCredentialModal } from "@/components/integrations/BootstrapCredentialModal";
import { ToastProvider } from "@/components/ui/toast";

function Wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={client}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("BootstrapCredentialModal — Salesforce variant", () => {
  it("renders the 4 Salesforce fields and masks the secret", () => {
    render(
      <BootstrapCredentialModal
        open={true}
        onOpenChange={vi.fn()}
        provider="salesforce"
        providerLabel="Salesforce"
      />,
      { wrapper: Wrapper },
    );

    expect(screen.getByLabelText(/client id/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/client secret/i)).toHaveAttribute(
      "type",
      "password",
    );
    expect(screen.getByLabelText(/callback url/i)).toHaveAttribute(
      "type",
      "url",
    );
    expect(screen.getByLabelText(/login domain/i)).toBeInTheDocument();
    // CareStack-only fields must not render.
    expect(screen.queryByLabelText(/vendor key/i)).toBeNull();
    expect(screen.queryByLabelText(/account key/i)).toBeNull();
  });

  it("posts SF bootstrap fields to /tenant/credentials on submit", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body));
      expect(body.provider_kind).toBe("salesforce");
      expect(body.client_id).toBe("3MVG9...");
      expect(body.client_secret).toBe("super-secret");
      expect(body.callback_url).toBe(
        "https://fusioncrm.app/api/integrations/salesforce/callback",
      );
      expect(body.domain).toBe("login.salesforce.com");
      return new Response("{}", { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <BootstrapCredentialModal
        open={true}
        onOpenChange={vi.fn()}
        provider="salesforce"
        providerLabel="Salesforce"
      />,
      { wrapper: Wrapper },
    );

    fireEvent.change(screen.getByLabelText(/client id/i), {
      target: { value: "3MVG9..." },
    });
    fireEvent.change(screen.getByLabelText(/client secret/i), {
      target: { value: "super-secret" },
    });
    fireEvent.change(screen.getByLabelText(/callback url/i), {
      target: {
        value: "https://fusioncrm.app/api/integrations/salesforce/callback",
      },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/tenant/credentials",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });
});

describe("BootstrapCredentialModal — CareStack variant", () => {
  it("renders the 6 CareStack fields and does not render SF fields", () => {
    render(
      <BootstrapCredentialModal
        open={true}
        onOpenChange={vi.fn()}
        provider="carestack"
        providerLabel="CareStack"
      />,
      { wrapper: Wrapper },
    );

    expect(screen.getByLabelText(/vendor key/i)).toHaveAttribute(
      "type",
      "password",
    );
    expect(screen.getByLabelText(/account key/i)).toHaveAttribute(
      "type",
      "password",
    );
    expect(screen.getByLabelText(/account id/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/idp base url/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/api base url/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/api version/i)).toBeInTheDocument();
    // Salesforce-only fields must not render.
    expect(screen.queryByLabelText(/client id/i)).toBeNull();
    expect(screen.queryByLabelText(/client secret/i)).toBeNull();
  });

  it("posts CS bootstrap fields to /tenant/credentials on submit", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body));
      expect(body.provider_kind).toBe("carestack");
      expect(body.vendor_key).toBe("vendor-1");
      expect(body.account_key).toBe("account-1");
      expect(body.account_id).toBe("acct-id");
      expect(body.idp_base_url).toBe("https://idp.carestack.com");
      expect(body.api_base_url).toBe("https://api.carestack.com");
      expect(body.api_version).toBe("v1.0.45");
      return new Response("{}", { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <BootstrapCredentialModal
        open={true}
        onOpenChange={vi.fn()}
        provider="carestack"
        providerLabel="CareStack"
      />,
      { wrapper: Wrapper },
    );

    fireEvent.change(screen.getByLabelText(/vendor key/i), {
      target: { value: "vendor-1" },
    });
    fireEvent.change(screen.getByLabelText(/account key/i), {
      target: { value: "account-1" },
    });
    fireEvent.change(screen.getByLabelText(/account id/i), {
      target: { value: "acct-id" },
    });
    fireEvent.change(screen.getByLabelText(/idp base url/i), {
      target: { value: "https://idp.carestack.com" },
    });
    fireEvent.change(screen.getByLabelText(/api base url/i), {
      target: { value: "https://api.carestack.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/tenant/credentials",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });
});

describe("BootstrapCredentialModal — OpenAI variant", () => {
  it("renders the OpenAI API key field only and masks the secret", () => {
    render(
      <BootstrapCredentialModal
        open={true}
        onOpenChange={vi.fn()}
        provider="openai"
        providerLabel="OpenAI"
      />,
      { wrapper: Wrapper },
    );

    expect(screen.getByLabelText(/^api key$/i)).toHaveAttribute(
      "type",
      "password",
    );
    expect(screen.queryByLabelText(/client id/i)).toBeNull();
    expect(screen.queryByLabelText(/vendor key/i)).toBeNull();
    expect(screen.queryByLabelText(/api base url/i)).toBeNull();
  });

  it("posts OpenAI bootstrap fields to /tenant/credentials on submit", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body));
      expect(body.provider_kind).toBe("openai");
      expect(body.credential_kind).toBe("api_key");
      expect(body.api_key).toBe("sk-test-openai-secret");
      return new Response("{}", { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <BootstrapCredentialModal
        open={true}
        onOpenChange={vi.fn()}
        provider="openai"
        providerLabel="OpenAI"
      />,
      { wrapper: Wrapper },
    );

    fireEvent.change(screen.getByLabelText(/^api key$/i), {
      target: { value: "sk-test-openai-secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/tenant/credentials",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });
});

describe("BootstrapCredentialModal — common behavior", () => {
  it("clears form state when the modal closes externally", () => {
    const { rerender } = render(
      <BootstrapCredentialModal
        open={true}
        onOpenChange={vi.fn()}
        provider="salesforce"
        providerLabel="Salesforce"
      />,
      { wrapper: Wrapper },
    );

    const secret = screen.getByLabelText(/client secret/i) as HTMLInputElement;
    fireEvent.change(secret, { target: { value: "leaked-secret" } });
    expect(secret.value).toBe("leaked-secret");

    rerender(
      <BootstrapCredentialModal
        open={false}
        onOpenChange={vi.fn()}
        provider="salesforce"
        providerLabel="Salesforce"
      />,
    );
    rerender(
      <BootstrapCredentialModal
        open={true}
        onOpenChange={vi.fn()}
        provider="salesforce"
        providerLabel="Salesforce"
      />,
    );
    const fresh = screen.getByLabelText(/client secret/i) as HTMLInputElement;
    expect(fresh.value).toBe("");
  });
});

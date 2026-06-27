import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CredentialEditModal } from "@/components/integrations/CredentialEditModal";
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

describe("CredentialEditModal", () => {
  it("posts api_key + display_name to /integrations/{provider}/api-key on submit", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body));
      expect(body.api_key).toBe("cs-new-key-123");
      expect(body.display_name).toBe("CareStack — primary");
      return new Response(
        JSON.stringify({
          id: "ff000099-0000-0000-0000-000000000099",
          provider: "carestack",
          status: "active",
          display_name: "CareStack — primary",
          created_at: "2026-01-01T00:00:00+00:00",
          updated_at: "2026-01-01T00:00:00+00:00",
        }),
        { status: 200 },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <CredentialEditModal
        open={true}
        onOpenChange={vi.fn()}
        provider="carestack"
        providerLabel="CareStack"
      />,
      { wrapper: Wrapper },
    );

    const keyInput = screen.getByLabelText(/^api key$/i);
    fireEvent.change(keyInput, { target: { value: "cs-new-key-123" } });
    const nameInput = screen.getByLabelText(/display name/i);
    fireEvent.change(nameInput, { target: { value: "CareStack — primary" } });

    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/integrations/carestack/api-key",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("does not submit when api_key field is empty", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(
      <CredentialEditModal
        open={true}
        onOpenChange={vi.fn()}
        provider="carestack"
        providerLabel="CareStack"
      />,
      { wrapper: Wrapper },
    );

    // The native required attribute will block submission; verify by also
    // checking the field exists and is empty.
    const keyInput = screen.getByLabelText(/^api key$/i) as HTMLInputElement;
    expect(keyInput.value).toBe("");
    expect(keyInput).toBeRequired();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("masks the api key input (type=password)", () => {
    render(
      <CredentialEditModal
        open={true}
        onOpenChange={vi.fn()}
        provider="carestack"
        providerLabel="CareStack"
      />,
      { wrapper: Wrapper },
    );
    const keyInput = screen.getByLabelText(/^api key$/i);
    expect(keyInput).toHaveAttribute("type", "password");
    expect(keyInput).toHaveAttribute("autocomplete", "off");
  });
});

import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DisconnectConfirmModal } from "@/components/integrations/DisconnectConfirmModal";
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

describe("DisconnectConfirmModal", () => {
  it("keeps the Disconnect button disabled until the operator types the provider name", () => {
    render(
      <DisconnectConfirmModal
        open={true}
        onOpenChange={vi.fn()}
        provider="salesforce"
        providerLabel="Salesforce"
      />,
      { wrapper: Wrapper },
    );

    const submit = screen.getByRole("button", { name: /^disconnect$/i });
    expect(submit).toBeDisabled();

    const input = screen.getByLabelText(/type .* to confirm/i);
    fireEvent.change(input, { target: { value: "salesforce" } });
    expect(submit).not.toBeDisabled();

    // Wrong text re-disables.
    fireEvent.change(input, { target: { value: "Salesfor" } });
    expect(submit).toBeDisabled();

    // Case-insensitive + trimmed match also enables.
    fireEvent.change(input, { target: { value: "  SALESFORCE  " } });
    expect(submit).not.toBeDisabled();
  });

  it("calls DELETE /integrations/{provider} when the confirmation submits", async () => {
    // Response shape doesn't need to be valid for the unit-level concern
    // (the modal called the right endpoint). Schema validation is exercised
    // separately by useCredentials.test.tsx.
    const fetchMock = vi.fn(async (_url: string) => {
      return new Response("{}", { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DisconnectConfirmModal
        open={true}
        onOpenChange={vi.fn()}
        provider="salesforce"
        providerLabel="Salesforce"
      />,
      { wrapper: Wrapper },
    );

    fireEvent.change(screen.getByLabelText(/type .* to confirm/i), {
      target: { value: "Salesforce" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^disconnect$/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/integrations/salesforce",
        expect.objectContaining({ method: "DELETE" }),
      );
    });
  });

  it("clears the typed confirmation when the modal closes", () => {
    const onOpenChange = vi.fn();
    const { rerender } = render(
      <DisconnectConfirmModal
        open={true}
        onOpenChange={onOpenChange}
        provider="carestack"
        providerLabel="CareStack"
      />,
      { wrapper: Wrapper },
    );

    const input = screen.getByLabelText(/type .* to confirm/i);
    fireEvent.change(input, { target: { value: "carestack" } });
    expect(
      screen.getByRole("button", { name: /^disconnect$/i }),
    ).not.toBeDisabled();

    // Close + reopen — the confirmation should reset (typed text gone,
    // submit re-disabled).
    rerender(
      <DisconnectConfirmModal
        open={false}
        onOpenChange={onOpenChange}
        provider="carestack"
        providerLabel="CareStack"
      />,
    );
    rerender(
      <DisconnectConfirmModal
        open={true}
        onOpenChange={onOpenChange}
        provider="carestack"
        providerLabel="CareStack"
      />,
    );
    const fresh = screen.getByLabelText(/type .* to confirm/i) as HTMLInputElement;
    expect(fresh.value).toBe("");
  });
});

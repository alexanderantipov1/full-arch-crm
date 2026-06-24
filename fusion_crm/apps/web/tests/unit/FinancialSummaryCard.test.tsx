import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PersonDetailPage from "@/app/(staff)/persons/[uid]/page";

const ALICE_UID = "11111111-1111-1111-1111-111111111111";

vi.mock("next/navigation", () => ({
  useParams: () => ({ uid: ALICE_UID }),
}));

type FetchInvocation = { url: string };

function installFetchSpy(
  router: (url: string) => Response | Promise<Response>,
): FetchInvocation[] {
  const log: FetchInvocation[] = [];
  const fetchMock = vi.fn(async (input: string | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    log.push({ url });
    return router(url);
  });
  vi.stubGlobal("fetch", fetchMock);
  return log;
}

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function basePersonDetail(extra: Record<string, unknown> = {}) {
  return {
    summary: {
      id: ALICE_UID,
      display_name: "Alice Morgan",
      email: "alice.morgan@example.com",
      phone: "+1 (415) 555-0142",
      has_lead: true,
      has_consultation: true,
      last_activity_at: "2026-05-04T18:32:00.000Z",
      source_providers: ["salesforce", "carestack"],
    },
    source_links: [
      {
        provider: "carestack",
        external_id: "PT-9981",
        entity: "Patient",
        confidence: 0.92,
      },
    ],
    lead: null,
    consultations: [],
    timeline: [],
    ...extra,
  };
}

function emptyJson() {
  return new Response("{}", { status: 200 });
}

function defaultRouter(detail: Record<string, unknown>) {
  return (url: string) => {
    if (url.startsWith("/api/persons/")) {
      return Promise.resolve(
        new Response(JSON.stringify(detail), { status: 200 }),
      );
    }
    if (url.startsWith("/api/ops/persons/")) {
      return Promise.resolve(new Response("[]", { status: 200 }));
    }
    if (url.startsWith("/api/tenant/current")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            tenant: { id: "00000000-0000-0000-0000-000000000001", name: "T" },
            locations: [],
          }),
          { status: 200 },
        ),
      );
    }
    if (url.startsWith("/api/sf/leads/")) {
      return Promise.resolve(emptyJson());
    }
    return Promise.resolve(emptyJson());
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("FinancialSummaryCard on PersonDetailPage", () => {
  it("renders Billed / Adjustments / Paid / Balance with currency when a snapshot is present", async () => {
    const detail = basePersonDetail({
      financial_summary: {
        billed: 12500,
        adjustments: -150,
        paid: 8500,
        balance: 3850,
        snapshot_received_at: "2026-05-25T12:00:00.000Z",
        carestack_patient_ids: ["PT-9981"],
        patient_count: 1,
      },
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Alice Morgan")).toBeInTheDocument(),
    );

    expect(screen.getByText("Billed")).toBeInTheDocument();
    expect(screen.getByText("Adjustments")).toBeInTheDocument();
    expect(screen.getByText("Paid")).toBeInTheDocument();
    expect(screen.getByText("Balance")).toBeInTheDocument();
    expect(screen.getByText("$12,500.00")).toBeInTheDocument();
    expect(screen.getByText("-$150.00")).toBeInTheDocument();
    expect(screen.getByText("$8,500.00")).toBeInTheDocument();
    expect(screen.getByText("$3,850.00")).toBeInTheDocument();
    expect(
      screen.getByText("Authoritative balance from CareStack"),
    ).toBeInTheDocument();
    // The "Read model pending" subhead from the stub Card must be gone.
    expect(screen.queryByText("Read model pending")).not.toBeInTheDocument();
  });

  it('renders four "—" + "No balance snapshot yet" when no snapshot has been captured', async () => {
    const detail = basePersonDetail({
      source_links: [
        {
          provider: "carestack",
          external_id: "PT-9985",
          entity: "Patient",
          confidence: 1.0,
        },
      ],
      financial_summary: {
        billed: 0,
        adjustments: 0,
        paid: 0,
        balance: 0,
        snapshot_received_at: null,
        carestack_patient_ids: ["PT-9985"],
        patient_count: 1,
      },
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Alice Morgan")).toBeInTheDocument(),
    );

    // "No balance snapshot yet" must surface BOTH as the card description
    // and as the timestamp line under the four numbers.
    const emptyMessages = screen.getAllByText("No balance snapshot yet");
    expect(emptyMessages.length).toBeGreaterThanOrEqual(1);
    // Every number renders "—" — never "$0".
    expect(screen.queryByText("$0.00")).not.toBeInTheDocument();
    // The four labels still appear so the operator knows the feature exists.
    expect(screen.getByText("Billed")).toBeInTheDocument();
    expect(screen.getByText("Balance")).toBeInTheDocument();
  });

  it("toggles a per-field description on the ? button click", async () => {
    const detail = basePersonDetail({
      financial_summary: {
        billed: 4448,
        adjustments: 0,
        paid: 4300,
        balance: 0,
        snapshot_received_at: "2026-05-25T12:00:00.000Z",
        carestack_patient_ids: ["PT-9981"],
        patient_count: 1,
      },
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Billed")).toBeInTheDocument(),
    );

    // Each row carries an accessible "What is <label>?" toggle, collapsed by default.
    const billedToggle = screen.getByRole("button", { name: "What is Billed?" });
    expect(billedToggle).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.queryByText(/PROCEDURECOMPLETED debit entries/i),
    ).not.toBeInTheDocument();

    fireEvent.click(billedToggle);
    expect(billedToggle).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByText(/PROCEDURECOMPLETED debit entries/i),
    ).toBeInTheDocument();

    // Clicking again collapses it.
    fireEvent.click(billedToggle);
    expect(billedToggle).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.queryByText(/PROCEDURECOMPLETED debit entries/i),
    ).not.toBeInTheDocument();

    // Other fields have their own toggles, independent of Billed.
    expect(
      screen.getByRole("button", { name: "What is Adjustments?" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "What is Paid?" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "What is Balance?" }),
    ).toBeInTheDocument();
  });

  it("opens a Help dialog and toggles EN/RU content", async () => {
    const detail = basePersonDetail({
      financial_summary: {
        billed: 2518,
        adjustments: 1000,
        paid: 7432,
        balance: 1896,
        snapshot_received_at: "2026-05-31T19:40:00.000Z",
        carestack_patient_ids: ["1461274", "2171827"],
        patient_count: 2,
      },
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Treatment / payments")).toBeInTheDocument(),
    );

    const helpButton = screen.getByRole("button", {
      name: "How to read Treatment / payments",
    });
    fireEvent.click(helpButton);

    // Dialog opens on EN by default.
    expect(
      screen.getByRole("heading", { name: "How to read this card" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/How much real money was collected/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Сколько реально получено денег/i),
    ).not.toBeInTheDocument();

    // Toggle to Russian.
    fireEvent.click(screen.getByRole("button", { name: "Русский" }));
    expect(
      screen.getByRole("heading", { name: "Как читать эту карточку" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Сколько реально получено денег/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/How much real money was collected/i),
    ).not.toBeInTheDocument();

    // Toggle back to English.
    fireEvent.click(screen.getByRole("button", { name: "English" }));
    expect(
      screen.getByRole("heading", { name: "How to read this card" }),
    ).toBeInTheDocument();
  });

  it("treats missing financial_summary the same as the empty state", async () => {
    const detail = basePersonDetail({ financial_summary: null });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Alice Morgan")).toBeInTheDocument(),
    );

    expect(
      screen.getAllByText("No balance snapshot yet").length,
    ).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("$0.00")).not.toBeInTheDocument();
  });
});

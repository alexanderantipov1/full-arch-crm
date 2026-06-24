import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import ProjectManagerPaymentsPage from "@/app/(staff)/project-manager/payments/page";

const PERSON_UID = "11111111-1111-1111-1111-111111111111";
const RAW_EVENT_ID = "ee000002-0000-0000-0000-000000000001";
const LOCATION_ID = "22222222-0000-0000-0000-000000000001";

function paymentRow(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "ff000003-0000-0000-0000-000000000201",
    person_uid: PERSON_UID,
    display_name: "Alice Payer",
    lead_status: "qualified",
    consultation_status: "completed",
    lead_source_label: "facebook",
    lead_owner: "Jane Owner",
    amount: 1850,
    kind: "payment_recorded",
    transaction_type: "PATIENTCREDIT",
    occurred_at: "2026-05-22T15:30:00.000Z",
    source_provider: "carestack",
    source_external_id: "CS-TX-9001",
    location_id: LOCATION_ID,
    location_name: "Fusion Roseville · Roseville",
    raw_event_id: RAW_EVENT_ID,
    invoice_id: "2424603",
    invoice_number: "10498",
    invoice_date: "2026-05-28",
    ...overrides,
  };
}

function paymentList(
  items: Array<Record<string, unknown>>,
  page: { total?: number; offset?: number; has_next?: boolean; has_previous?: boolean } = {},
) {
  return {
    items,
    total: page.total ?? items.length,
    limit: 100,
    offset: page.offset ?? 0,
    has_next: page.has_next ?? false,
    has_previous: page.has_previous ?? false,
    filters: {
      from: null,
      to: null,
      source_provider: null,
      lead_source: null,
      location_id: null,
      q: null,
    },
  };
}

function paymentSummary(over: Partial<Record<string, unknown>> = {}) {
  return {
    collected_total: 5622.5,
    payment_count: 7,
    patient_count: 5,
    filters: {
      from: null,
      to: null,
      source_provider: null,
      lead_source: null,
      location_id: null,
      q: null,
    },
    ...over,
  };
}

function rawEvent() {
  return {
    id: RAW_EVENT_ID,
    provider: "carestack",
    external_id: "CS-TX-9001",
    kind: "carestack.accounting_transaction.upsert",
    fetched_at: "2026-05-22T15:30:00.000Z",
    sync_run_id: "ff000001-0000-0000-0000-000000000005",
    resolved_person_uid: PERSON_UID,
    payload: {
      id: "CS-TX-9001",
      amount: 1850,
      transactionType: "PATIENTCREDIT",
      isReversed: false,
      locationId: LOCATION_ID,
    },
  };
}

type FetchInvocation = { url: string; init?: RequestInit };

function installFetchSpy(
  router: (url: string) => Response | Promise<Response>,
): FetchInvocation[] {
  const log: FetchInvocation[] = [];
  const fetchMock = vi.fn(async (input: string | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    log.push({ url, init });
    return router(url);
  });
  vi.stubGlobal("fetch", fetchMock);
  return log;
}

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}


// ENG-410: the page defaults to the grouped (same-day) view. Flat-list
// tests opt out by unchecking "Group by day" right after render.
async function disableGrouping() {
  const user = userEvent.setup();
  await user.click(
    screen.getByLabelText(/Group same-day payments per person/i),
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("ProjectManagerPaymentsPage", () => {
  it("shows loading then renders payment rows", async () => {
    installFetchSpy((url) => {
      if (url.startsWith("/api/dashboard/pm/payments/summary")) {
        return Promise.resolve(
          new Response(JSON.stringify(paymentSummary()), { status: 200 }),
        );
      }
      if (url.startsWith("/api/dashboard/pm/payments")) {
        return Promise.resolve(
          new Response(JSON.stringify(paymentList([paymentRow()])), {
            status: 200,
          }),
        );
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    });

    render(<ProjectManagerPaymentsPage />, { wrapper });
    await disableGrouping();

    // Initial loading state.
    expect(screen.getByRole("heading", { name: /Payments/i })).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("Alice Payer")).toBeInTheDocument(),
    );
    expect(screen.getByText("CS-TX-9001")).toBeInTheDocument();
    // Currency rendering — once in the row, once in the total header.
    expect(screen.getAllByText(/\$1,850\.00/).length).toBeGreaterThanOrEqual(1);
    // ENG-408: per-row acquisition attribution replaces the Stage badge.
    expect(screen.getByText("facebook")).toBeInTheDocument();
    expect(screen.getByText("Jane Owner")).toBeInTheDocument();
    expect(
      screen.getByText("Fusion Roseville · Roseville"),
    ).toBeInTheDocument();
    // ENG-303: invoice number + invoice date columns.
    expect(screen.getByText("#10498")).toBeInTheDocument();
    expect(screen.getByText("May 28, 2026")).toBeInTheDocument();
  });

  it("shows an em dash in the Invoice column when no invoice is linked", async () => {
    installFetchSpy((url) => {
      if (url.startsWith("/api/dashboard/pm/payments/summary")) {
        return Promise.resolve(
          new Response(JSON.stringify(paymentSummary()), { status: 200 }),
        );
      }
      if (url.startsWith("/api/dashboard/pm/payments")) {
        return Promise.resolve(
          new Response(
            JSON.stringify(
              paymentList([
                paymentRow({
                  display_name: "No Invoice Payer",
                  invoice_id: null,
                  invoice_number: null,
                  invoice_date: null,
                }),
              ]),
            ),
            { status: 200 },
          ),
        );
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    });

    render(<ProjectManagerPaymentsPage />, { wrapper });
    await disableGrouping();
    await waitFor(() =>
      expect(screen.getByText("No Invoice Payer")).toBeInTheDocument(),
    );
    expect(screen.queryByText("#10498")).not.toBeInTheDocument();
  });

  it("auto-applies filters on change (no Apply button)", async () => {
    const log = installFetchSpy((url) => {
      if (url.startsWith("/api/dashboard/pm/payments/summary")) {
        return Promise.resolve(
          new Response(JSON.stringify(paymentSummary()), { status: 200 }),
        );
      }
      if (url.startsWith("/api/dashboard/pm/payments")) {
        if (url.includes("source_provider=carestack")) {
          return Promise.resolve(
            new Response(
              JSON.stringify(
                paymentList([
                  paymentRow({
                    display_name: "Filtered Person",
                    source_external_id: "CS-TX-NEW",
                    raw_event_id: RAW_EVENT_ID,
                  }),
                ]),
              ),
              { status: 200 },
            ),
          );
        }
        return Promise.resolve(
          new Response(JSON.stringify(paymentList([paymentRow()])), {
            status: 200,
          }),
        );
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    });

    const user = userEvent.setup();
    render(<ProjectManagerPaymentsPage />, { wrapper });
    await disableGrouping();
    await waitFor(() =>
      expect(screen.getByText("Alice Payer")).toBeInTheDocument(),
    );

    // ENG-408: no Apply button — changing a select refetches immediately.
    expect(
      screen.queryByRole("button", { name: /^Filter$/i }),
    ).not.toBeInTheDocument();

    const providerSelect = screen.getByLabelText(/Provider/i);
    await user.selectOptions(providerSelect, "carestack");

    await waitFor(() =>
      expect(screen.getByText("Filtered Person")).toBeInTheDocument(),
    );

    const paymentsCalls = log.filter((c) =>
      c.url.startsWith("/api/dashboard/pm/payments"),
    );
    // First load + after-filter refetch.
    expect(paymentsCalls.length).toBeGreaterThanOrEqual(2);
    expect(paymentsCalls.at(-1)!.url).toContain("source_provider=carestack");
  });

  it("filters by a lead-source resource node from the Source dropdown (ENG-408)", async () => {
    const tree = {
      total_leads: 100,
      consults_scheduled: 10,
      consults_attended: 5,
      collected_amount: 1000,
      sources: [
        {
          key: "facebook",
          label: "facebook",
          level: "channel",
          leads: 80,
          consults_scheduled: 8,
          consults_attended: 4,
          collected_amount: 900,
          children: [
            {
              key: "facebook/facebook",
              label: "facebook",
              level: "source",
              leads: 80,
              consults_scheduled: 8,
              consults_attended: 4,
              collected_amount: 900,
              children: [],
            },
          ],
        },
      ],
    };
    const log = installFetchSpy((url) => {
      if (url.startsWith("/api/ops/analytics/lead-sources/tree")) {
        return Promise.resolve(
          new Response(JSON.stringify(tree), { status: 200 }),
        );
      }
      if (url.startsWith("/api/dashboard/pm/payments/summary")) {
        return Promise.resolve(
          new Response(JSON.stringify(paymentSummary()), { status: 200 }),
        );
      }
      if (url.startsWith("/api/dashboard/pm/payments")) {
        const items = url.includes("lead_channel=facebook")
          ? [
              paymentRow({
                display_name: "Facebook Payer",
                source_external_id: "CS-TX-FB",
              }),
            ]
          : [paymentRow()];
        return Promise.resolve(
          new Response(JSON.stringify(paymentList(items)), { status: 200 }),
        );
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    });

    const user = userEvent.setup();
    render(<ProjectManagerPaymentsPage />, { wrapper });
    await disableGrouping();
    await waitFor(() =>
      expect(screen.getByText("Alice Payer")).toBeInTheDocument(),
    );

    const sourceSelect = screen.getByLabelText(/Lead source resource/i);
    await waitFor(() =>
      expect(within(sourceSelect).getAllByRole("option").length).toBeGreaterThan(1),
    );
    await user.selectOptions(
      sourceSelect,
      JSON.stringify({ channel: "facebook" }),
    );

    await waitFor(() =>
      expect(screen.getByText("Facebook Payer")).toBeInTheDocument(),
    );

    const lastList = log
      .filter(
        (c) =>
          c.url.startsWith("/api/dashboard/pm/payments") &&
          !c.url.includes("/summary"),
      )
      .at(-1)!;
    expect(lastList.url).toContain("lead_channel=facebook");
    // The summary bar honours the node too — "cash from this resource".
    const lastSummary = log
      .filter((c) => c.url.startsWith("/api/dashboard/pm/payments/summary"))
      .at(-1)!;
    expect(lastSummary.url).toContain("lead_channel=facebook");
  });

  it("excludes payment_applied by default and requests them via Show applied (backend-driven)", async () => {
    const appliedRow = paymentRow({
      id: "ff000003-0000-0000-0000-000000000204",
      display_name: "Applied Payer",
      source_external_id: "CS-TX-9004",
      kind: "payment_applied",
      transaction_type: "PATPAYMENTAPPLIED",
    });
    const log = installFetchSpy((url) => {
      if (url.startsWith("/api/dashboard/pm/payments/summary")) {
        return Promise.resolve(
          new Response(JSON.stringify(paymentSummary()), { status: 200 }),
        );
      }
      if (url.startsWith("/api/dashboard/pm/payments")) {
        // The API decides what to return based on include_applied — the
        // page no longer filters client-side.
        const items = url.includes("include_applied=true")
          ? [paymentRow(), appliedRow]
          : [paymentRow()];
        return Promise.resolve(
          new Response(JSON.stringify(paymentList(items)), { status: 200 }),
        );
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    });

    const user = userEvent.setup();
    render(<ProjectManagerPaymentsPage />, { wrapper });
    await disableGrouping();
    await waitFor(() =>
      expect(screen.getByText("Alice Payer")).toBeInTheDocument(),
    );

    // Default load did NOT request applied rows, and none are shown.
    expect(screen.queryByText("Applied Payer")).not.toBeInTheDocument();
    expect(
      log.some(
        (c) =>
          c.url.startsWith("/api/dashboard/pm/payments") &&
          c.url.includes("include_applied=true"),
      ),
    ).toBe(false);

    // Toggle "Show applied" — the page refetches WITH include_applied=true
    // and the allocation row arrives from the API.
    await user.click(
      screen.getByLabelText(/Show applied \(allocation\) rows/i),
    );
    await waitFor(() =>
      expect(screen.getByText("Applied Payer")).toBeInTheDocument(),
    );

    const lastCall = log
      .filter((c) => c.url.startsWith("/api/dashboard/pm/payments"))
      .at(-1)!;
    expect(lastCall.url).toContain("include_applied=true");
    // Per-row kind label is the human-readable type, not the raw kind.
    expect(screen.getByText("Payment")).toBeInTheDocument();
    expect(screen.getByText("Applied")).toBeInTheDocument();
  });

  it("paginates via Next using the server's offset/has_next", async () => {
    const log = installFetchSpy((url) => {
      if (url.startsWith("/api/dashboard/pm/payments/summary")) {
        return Promise.resolve(
          new Response(JSON.stringify(paymentSummary()), { status: 200 }),
        );
      }
      if (url.startsWith("/api/dashboard/pm/payments")) {
        const onPageTwo = url.includes("offset=100");
        const items = onPageTwo
          ? [
              paymentRow({
                id: "ff000003-0000-0000-0000-000000000302",
                display_name: "Older Payer",
                source_external_id: "CS-TX-OLD",
              }),
            ]
          : [paymentRow()];
        return Promise.resolve(
          new Response(
            JSON.stringify(
              paymentList(items, {
                total: 101,
                offset: onPageTwo ? 100 : 0,
                has_next: !onPageTwo,
                has_previous: onPageTwo,
              }),
            ),
            { status: 200 },
          ),
        );
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    });

    const user = userEvent.setup();
    render(<ProjectManagerPaymentsPage />, { wrapper });
    await disableGrouping();
    await waitFor(() =>
      expect(screen.getByText("Alice Payer")).toBeInTheDocument(),
    );
    // Honest total is surfaced (header range + footer), not just page count.
    expect(screen.getAllByText(/of 101/).length).toBeGreaterThanOrEqual(1);

    await user.click(screen.getByRole("button", { name: /^Next$/i }));
    await waitFor(() =>
      expect(screen.getByText("Older Payer")).toBeInTheDocument(),
    );

    const lastCall = log
      .filter((c) => c.url.startsWith("/api/dashboard/pm/payments"))
      .at(-1)!;
    expect(lastCall.url).toContain("offset=100");
  });

  it("renders the window-wide summary bar (Collected / Payments / Patients)", async () => {
    const log = installFetchSpy((url) => {
      if (url.startsWith("/api/dashboard/pm/payments/summary")) {
        return Promise.resolve(
          new Response(
            JSON.stringify(
              paymentSummary({
                collected_total: 205639.05,
                payment_count: 565,
                patient_count: 312,
              }),
            ),
            { status: 200 },
          ),
        );
      }
      if (url.startsWith("/api/dashboard/pm/payments")) {
        return Promise.resolve(
          new Response(JSON.stringify(paymentList([paymentRow()])), {
            status: 200,
          }),
        );
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    });

    render(<ProjectManagerPaymentsPage />, { wrapper });
    await disableGrouping();

    // Window-wide totals from the summary endpoint, not the page sum.
    await waitFor(() =>
      expect(screen.getByText("$205,639.05")).toBeInTheDocument(),
    );
    expect(screen.getByText("565")).toBeInTheDocument();
    expect(screen.getByText("312")).toBeInTheDocument();
    expect(screen.getByText("Collected")).toBeInTheDocument();
    expect(screen.getByText("Patients")).toBeInTheDocument();

    // The summary endpoint was actually called.
    expect(
      log.some((c) =>
        c.url.startsWith("/api/dashboard/pm/payments/summary"),
      ),
    ).toBe(true);
  });

  it("renders the per-row balance pill from the row's balance field (ENG-306)", async () => {
    installFetchSpy((url) => {
      if (url.startsWith("/api/dashboard/pm/payments/summary")) {
        return Promise.resolve(
          new Response(JSON.stringify(paymentSummary()), { status: 200 }),
        );
      }
      if (url.startsWith("/api/dashboard/pm/payments")) {
        const items = [
          paymentRow({
            id: "ff000003-0000-0000-0000-000000000301",
            display_name: "Snapshot Payer",
            balance: 1250,
          }),
          paymentRow({
            id: "ff000003-0000-0000-0000-000000000302",
            display_name: "No Snapshot Payer",
            source_external_id: "CS-TX-NONE",
            balance: null,
          }),
        ];
        return Promise.resolve(
          new Response(JSON.stringify(paymentList(items)), { status: 200 }),
        );
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    });

    render(<ProjectManagerPaymentsPage />, { wrapper });
    await disableGrouping();
    await waitFor(() =>
      expect(screen.getByText("Snapshot Payer")).toBeInTheDocument(),
    );

    // Pill renders the balance for the snapshotted row...
    const snapshotPill = screen.getByLabelText(/Outstanding balance: \$1,250/i);
    expect(snapshotPill).toHaveTextContent("$1,250.00");
    // ...and a literal em-dash (NOT "$0.00") for the unsnapshotted row.
    const emptyPill = screen.getByLabelText(/No balance snapshot captured yet/i);
    expect(emptyPill).toHaveTextContent("—");
    // No "$0.00" anywhere on the page — the empty-state contract.
    expect(screen.queryByText("$0.00")).not.toBeInTheDocument();
  });

  it("opens the View raw drilldown and renders the payload", async () => {
    installFetchSpy((url) => {
      if (url.startsWith("/api/dashboard/pm/payments/summary")) {
        return Promise.resolve(
          new Response(JSON.stringify(paymentSummary()), { status: 200 }),
        );
      }
      if (url.startsWith("/api/dashboard/pm/payments")) {
        return Promise.resolve(
          new Response(JSON.stringify(paymentList([paymentRow()])), {
            status: 200,
          }),
        );
      }
      if (url.startsWith("/api/ingest/dev/inspector/raw-events/")) {
        return Promise.resolve(
          new Response(JSON.stringify(rawEvent()), { status: 200 }),
        );
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    });

    const user = userEvent.setup();
    render(<ProjectManagerPaymentsPage />, { wrapper });
    await disableGrouping();
    await waitFor(() =>
      expect(screen.getByText("Alice Payer")).toBeInTheDocument(),
    );

    const viewRaw = screen.getByRole("button", {
      name: /View raw payload for Alice Payer/i,
    });
    await user.click(viewRaw);

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Raw payload/i)).toBeInTheDocument();
    // The verbatim payload renders as pretty JSON; assert a couple of its
    // structured fields surface.
    await waitFor(() => {
      const text = dialog.textContent ?? "";
      expect(text).toContain("CS-TX-9001");
      expect(text).toContain("PATIENTCREDIT");
    });
  });

  it("groups same-day legs per person by default and expands them (ENG-410)", async () => {
    const legA = paymentRow({
      id: "ff000003-0000-0000-0000-000000000401",
      display_name: "Christopher Bustos",
      amount: 450,
      invoice_number: "10854",
      source_external_id: "66198820",
      occurred_at: "2026-06-11T17:27:00.000Z",
    });
    const legB = paymentRow({
      id: "ff000003-0000-0000-0000-000000000402",
      display_name: "Christopher Bustos",
      amount: 344,
      invoice_number: "10855",
      source_external_id: "66199075",
      occurred_at: "2026-06-11T17:28:00.000Z",
    });
    const soloLeg = paymentRow({
      id: "ff000003-0000-0000-0000-000000000403",
      person_uid: "11111111-1111-1111-1111-222222222222",
      display_name: "Sophia Bezuglov",
      amount: 129.2,
      invoice_number: "10858",
      source_external_id: "66225656",
      occurred_at: "2026-06-11T19:48:00.000Z",
    });
    const groups = {
      items: [
        {
          person_uid: PERSON_UID,
          display_name: "Christopher Bustos",
          lead_status: "qualified",
          consultation_status: "completed",
          lead_source_label: "google",
          lead_owner: "Yelena Myalik",
          balance: 1254,
          kind: "payment_recorded",
          day: "2026-06-11",
          amount: 794,
          leg_count: 2,
          occurred_at: "2026-06-11T17:28:00.000Z",
          legs: [legB, legA],
        },
        {
          person_uid: soloLeg.person_uid,
          display_name: "Sophia Bezuglov",
          lead_status: null,
          consultation_status: null,
          lead_source_label: null,
          lead_owner: null,
          balance: 0,
          kind: "payment_recorded",
          day: "2026-06-11",
          amount: 129.2,
          leg_count: 1,
          occurred_at: soloLeg.occurred_at,
          legs: [soloLeg],
        },
      ],
      total: 2,
      limit: 100,
      offset: 0,
      has_next: false,
      has_previous: false,
      filters: {
        from: null,
        to: null,
        source_provider: null,
        lead_source: null,
        location_id: null,
        q: null,
      },
    };
    installFetchSpy((url) => {
      if (url.startsWith("/api/dashboard/pm/payments/groups")) {
        return Promise.resolve(
          new Response(JSON.stringify(groups), { status: 200 }),
        );
      }
      if (url.startsWith("/api/dashboard/pm/payments/summary")) {
        return Promise.resolve(
          new Response(JSON.stringify(paymentSummary()), { status: 200 }),
        );
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    });

    const user = userEvent.setup();
    render(<ProjectManagerPaymentsPage />, { wrapper });

    // Grouped is the DEFAULT — no toggle needed; the two-leg group renders
    // as ONE row with the summed amount and a ×2 badge.
    await waitFor(() =>
      expect(screen.getByText("Christopher Bustos")).toBeInTheDocument(),
    );
    expect(screen.getAllByText(/\$794\.00/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Payment ×2/)).toBeInTheDocument();
    expect(screen.getByText("2 legs · same day")).toBeInTheDocument();
    expect(screen.getByText("2 invoices")).toBeInTheDocument();
    // Legs are hidden until expansion.
    expect(screen.queryByText("66198820")).not.toBeInTheDocument();
    // Single-leg group renders like a plain row (no chevron semantics).
    expect(screen.getByText("Sophia Bezuglov")).toBeInTheDocument();
    expect(screen.getByText("66225656")).toBeInTheDocument();

    // Expanding shows the underlying legs with their own invoices.
    await user.click(
      screen.getByRole("button", {
        name: /Toggle 2 payment legs for Christopher Bustos/i,
      }),
    );
    expect(screen.getByText("66198820")).toBeInTheDocument();
    expect(screen.getByText("66199075")).toBeInTheDocument();
    expect(screen.getByText("#10854")).toBeInTheDocument();
    expect(screen.getByText("#10855")).toBeInTheDocument();
    expect(screen.getByText("$450.00")).toBeInTheDocument();
    expect(screen.getByText("$344.00")).toBeInTheDocument();
  });
});

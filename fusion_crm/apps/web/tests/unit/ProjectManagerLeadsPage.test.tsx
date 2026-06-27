import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import ProjectManagerLeadsPage from "@/app/(staff)/project-manager/leads/page";

const SF_PERSON = "aaaa1111-1111-1111-1111-111111111111";
const CS_PERSON = "bbbb2222-2222-2222-2222-222222222222";
const UNIFIED_PERSON = "cccc3333-3333-3333-3333-333333333333";

function appliedFilters() {
  return {
    from: null,
    to: null,
    source_provider: null,
    lead_source: null,
    location_id: null,
    q: null,
  };
}

function leadRow(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "ffff0000-0000-0000-0000-000000000001",
    person_uid: SF_PERSON,
    display_name: "SF Lead One",
    given_name: "SF",
    family_name: "One",
    email: "sf-one@example.com",
    phone: null,
    status: "qualified",
    lead_source: "Website",
    source_provider: "salesforce",
    source_external_id: "00Q-1001",
    created_at: "2026-05-20T15:30:00.000Z",
    updated_at: "2026-05-21T09:00:00.000Z",
    source_providers: ["salesforce"],
    ...overrides,
  };
}

function leadList(
  items: Array<Record<string, unknown>>,
  page: {
    total?: number;
    offset?: number;
    has_next?: boolean;
    has_previous?: boolean;
  } = {},
) {
  return {
    items,
    total: page.total ?? items.length,
    limit: 50,
    offset: page.offset ?? 0,
    has_next: page.has_next ?? false,
    has_previous: page.has_previous ?? false,
    filters: appliedFilters(),
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

function leadsResponse(url: string): Response {
  // Each provider column drives its own server-filtered query; route by the
  // source_provider query param the column appended.
  if (url.includes("source_provider=salesforce")) {
    const onPageTwo = url.includes("offset=50");
    const items = onPageTwo
      ? [
          leadRow({
            id: "ffff0000-0000-0000-0000-000000000002",
            display_name: "SF Lead Two",
            source_external_id: "00Q-1002",
          }),
        ]
      : [leadRow()];
    return new Response(
      JSON.stringify(
        leadList(items, {
          total: 62309,
          offset: onPageTwo ? 50 : 0,
          has_next: true,
          has_previous: onPageTwo,
        }),
      ),
      { status: 200 },
    );
  }
  if (url.includes("source_provider=carestack")) {
    return new Response(
      JSON.stringify(
        leadList(
          [
            leadRow({
              id: "ffff0000-0000-0000-0000-000000000101",
              person_uid: CS_PERSON,
              display_name: "CS Patient One",
              source_provider: "carestack",
              source_external_id: "CS-5001",
              source_providers: ["carestack"],
            }),
          ],
          { total: 55849, offset: 0, has_next: true, has_previous: false },
        ),
      ),
      { status: 200 },
    );
  }
  // Linked tab (linked_only=true) — irrelevant to the All-tab assertions.
  return new Response(JSON.stringify(leadList([])), { status: 200 });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("ProjectManagerLeadsPage — All leads provider split", () => {
  async function renderAllTab() {
    const log = installFetchSpy((url) => {
      if (url.startsWith("/api/dashboard/pm/leads")) {
        return Promise.resolve(leadsResponse(url));
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    });
    const user = userEvent.setup();
    render(<ProjectManagerLeadsPage />, { wrapper });
    // Page defaults to the Galleria location tab; switch to All leads.
    await user.click(screen.getByRole("button", { name: /All leads/i }));
    return { log, user };
  }

  it("drives the Salesforce column from a source_provider=salesforce query", async () => {
    const { log } = await renderAllTab();

    await waitFor(() =>
      expect(screen.getByText("SF Lead One")).toBeInTheDocument(),
    );

    // The SF column issued a salesforce-scoped query.
    const leadCalls = log.filter((c) =>
      c.url.startsWith("/api/dashboard/pm/leads"),
    );
    expect(
      leadCalls.some((c) => c.url.includes("source_provider=salesforce")),
    ).toBe(true);
    expect(
      leadCalls.some((c) => c.url.includes("source_provider=carestack")),
    ).toBe(true);

    // The per-provider total is the authoritative count, not the page size.
    expect(screen.getByText(/Showing 1–1 of 62309/)).toBeInTheDocument();
    // CareStack column renders its own provider-specific rows + total.
    expect(screen.getByText("CS Patient One")).toBeInTheDocument();
    expect(screen.getByText(/Showing 1–1 of 55849/)).toBeInTheDocument();
  });

  it("advances the SF column's offset independently of CareStack", async () => {
    const { log, user } = await renderAllTab();

    await waitFor(() =>
      expect(screen.getByText("SF Lead One")).toBeInTheDocument(),
    );

    // Locate the Salesforce card by its accent class and click its Next.
    const sfHeading = screen.getByText("Salesforce");
    const sfRoot = sfHeading.closest("[class*='border-blue']") as HTMLElement;
    const sfNext = within(sfRoot).getByRole("button", { name: /^Next$/i });
    await user.click(sfNext);

    await waitFor(() =>
      expect(screen.getByText("SF Lead Two")).toBeInTheDocument(),
    );

    // The SF column refetched at offset=50; the CareStack column did NOT.
    const sfCalls = log.filter(
      (c) =>
        c.url.startsWith("/api/dashboard/pm/leads") &&
        c.url.includes("source_provider=salesforce"),
    );
    const csCalls = log.filter(
      (c) =>
        c.url.startsWith("/api/dashboard/pm/leads") &&
        c.url.includes("source_provider=carestack"),
    );

    expect(sfCalls.at(-1)!.url).toContain("offset=50");
    // CareStack never requested offset=50 — its pagination is independent.
    expect(csCalls.every((c) => !c.url.includes("offset=50"))).toBe(true);
    // The CareStack column still shows page one.
    expect(screen.getByText("CS Patient One")).toBeInTheDocument();
  });
});

// ENG-561: location tabs + unified person card.
describe("ProjectManagerLeadsPage — location tabs + unified card", () => {
  // A person that exists on BOTH providers, returned for the galleria tab.
  function unifiedGalleriaList() {
    return leadList(
      [
        leadRow({
          id: "ffff0000-0000-0000-0000-00000000aa01",
          person_uid: UNIFIED_PERSON,
          display_name: "Unified Person",
          source_provider: "salesforce",
          source_external_id: "00Q-9001",
          lead_source: "Website",
          source_providers: ["salesforce", "carestack"],
          created_at: "2026-04-01T10:00:00.000Z",
        }),
        leadRow({
          id: "ffff0000-0000-0000-0000-00000000aa02",
          person_uid: UNIFIED_PERSON,
          display_name: "Unified Person",
          status: "carestack_patient",
          source_provider: "carestack",
          source_external_id: "CS-9001",
          source_providers: ["salesforce", "carestack"],
          created_at: "2026-04-10T12:00:00.000Z",
          consultation_provider: "carestack",
          consultation_status: "scheduled",
          consultation_scheduled_at: "2026-04-20T17:00:00.000Z",
          location_name: "Galleria",
        }),
      ],
      { total: 1 },
    );
  }

  function locationRouter(url: string): Response {
    if (url.startsWith("/api/dashboard/pm/leads")) {
      if (url.includes("location_tab=galleria")) {
        return new Response(JSON.stringify(unifiedGalleriaList()), {
          status: 200,
        });
      }
      // Other tabs / queries are irrelevant here.
      return new Response(JSON.stringify(leadList([])), { status: 200 });
    }
    return new Response("{}", { status: 200 });
  }

  it("defaults to the Galleria tab and queries location_tab=galleria on first load", async () => {
    const log = installFetchSpy((url) => Promise.resolve(locationRouter(url)));
    render(<ProjectManagerLeadsPage />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Unified Person")).toBeInTheDocument(),
    );

    const leadCalls = log.filter((c) =>
      c.url.startsWith("/api/dashboard/pm/leads"),
    );
    // The very first leads query carries the galleria tab — no click needed.
    expect(leadCalls.length).toBeGreaterThan(0);
    expect(leadCalls.every((c) => c.url.includes("location_tab=galleria"))).toBe(
      true,
    );
    // "all"/"linked" params must NOT leak onto a location query.
    expect(leadCalls.some((c) => c.url.includes("linked_only"))).toBe(false);
  });

  it("loads persons when switching to another location tab", async () => {
    const seen: string[] = [];
    const log = installFetchSpy((url) => {
      seen.push(url);
      return Promise.resolve(locationRouter(url));
    });
    const user = userEvent.setup();
    render(<ProjectManagerLeadsPage />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Unified Person")).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: /El Dorado/i }));

    await waitFor(() =>
      expect(
        log.some((c) => c.url.includes("location_tab=el_dorado")),
      ).toBe(true),
    );
  });

  it("renders a unified card showing Salesforce and CareStack together", async () => {
    installFetchSpy((url) => Promise.resolve(locationRouter(url)));
    const user = userEvent.setup();
    render(<ProjectManagerLeadsPage />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Unified Person")).toBeInTheDocument(),
    );

    // Both providers are represented on the same card (not two bare columns).
    expect(screen.getByText("Salesforce")).toBeInTheDocument();
    expect(screen.getByText("CareStack")).toBeInTheDocument();

    // The person name stays a navigable link (separate from the expand control),
    // and the expand toggle is a real button — no nested interactive markup.
    expect(
      screen.getByRole("link", { name: "Unified Person" }),
    ).toHaveAttribute("href", `/persons/${UNIFIED_PERSON}`);

    // Expanding the card reveals the merged SF→CareStack timeline path.
    await user.click(screen.getByRole("button", { name: /expand details/i }));

    await waitFor(() =>
      expect(screen.getByText(/SF lead created/i)).toBeInTheDocument(),
    );
    expect(screen.getByText(/CareStack patient since/i)).toBeInTheDocument();
    expect(screen.getByText(/CS appointment/i)).toBeInTheDocument();
  });
});

describe("ProjectManagerLeadsPage — provider blocks + sort toggle", () => {
  // A person linked to BOTH providers but returned as a SINGLE Salesforce row:
  // the CareStack consultation rides on the SF row (the Flora case). Presence
  // must come from source_providers + consultation_provider, not row count.
  function singleSfLinkedList() {
    return leadList(
      [
        leadRow({
          id: "ffff0000-0000-0000-0000-0000000000f1",
          person_uid: UNIFIED_PERSON,
          display_name: "Flora Linked",
          source_provider: "salesforce",
          source_external_id: "00Q-FLORA",
          lead_source: "Referral",
          status: "qualified",
          source_providers: ["salesforce", "carestack"],
          created_at: "2025-10-13T18:41:07.000Z",
          consultation_provider: "carestack",
          consultation_status: "scheduled",
          consultation_provider_created_at: "2026-06-18T17:42:00.000Z",
          consultation_scheduled_at: "2026-06-25T16:00:00.000Z",
          location_name: "Galleria Oral Surgery & Dental Implants · Roseville",
        }),
      ],
      { total: 1 },
    );
  }

  function router(url: string): Response {
    if (url.startsWith("/api/dashboard/pm/leads")) {
      if (url.includes("location_tab=galleria")) {
        return new Response(JSON.stringify(singleSfLinkedList()), {
          status: 200,
        });
      }
      return new Response(JSON.stringify(leadList([])), { status: 200 });
    }
    return new Response("{}", { status: 200 });
  }

  it("marks a single-SF-row person linked to CareStack as CareStack (not 'No CareStack')", async () => {
    installFetchSpy((url) => Promise.resolve(router(url)));
    render(<ProjectManagerLeadsPage />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Flora Linked")).toBeInTheDocument(),
    );

    // Presence is derived from links, so both badges read positive.
    expect(screen.getByText("CareStack")).toBeInTheDocument();
    expect(screen.queryByText("No CareStack")).not.toBeInTheDocument();
    expect(screen.getByText("Salesforce")).toBeInTheDocument();
  });

  it("shows symmetric Salesforce + CareStack detail blocks when expanded", async () => {
    const user = userEvent.setup();
    installFetchSpy((url) => Promise.resolve(router(url)));
    render(<ProjectManagerLeadsPage />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Flora Linked")).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /expand details/i }));

    // Salesforce block (lead details). "Source" alone collides with the filter
    // form label, so assert on the block-unique fields.
    expect(screen.getByText("Salesforce lead")).toBeInTheDocument();
    expect(screen.getByText("Referral")).toBeInTheDocument();
    expect(screen.getByText("SF Lead #")).toBeInTheDocument();
    expect(screen.getByText("00Q-FLORA")).toBeInTheDocument();

    // CareStack block (appointment details) — even though there is no separate
    // CareStack row, the appointment fields ride on the SF row.
    expect(screen.getByText("Booked")).toBeInTheDocument();
    expect(screen.getByText("Appointment")).toBeInTheDocument();
    expect(screen.getByText("Location")).toBeInTheDocument();
  });

  it("flips the server sort to appointment when the CareStack sort header is clicked", async () => {
    const user = userEvent.setup();
    const log = installFetchSpy((url) => Promise.resolve(router(url)));
    render(<ProjectManagerLeadsPage />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Flora Linked")).toBeInTheDocument(),
    );

    const leadCalls = () =>
      log.filter((c) => c.url.startsWith("/api/dashboard/pm/leads"));
    // Default ordering is lead/funnel date.
    expect(leadCalls().some((c) => c.url.includes("sort=lead"))).toBe(true);
    expect(leadCalls().some((c) => c.url.includes("sort=appointment"))).toBe(
      false,
    );

    await user.click(
      screen.getByRole("button", { name: /CareStack appointment/i }),
    );

    await waitFor(() =>
      expect(
        leadCalls().some((c) => c.url.includes("sort=appointment")),
      ).toBe(true),
    );
  });
});

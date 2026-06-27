import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PersonDetailPage from "@/app/(staff)/persons/[uid]/page";

const PERSON_UID = "55555555-aaaa-4444-bbbb-cccccccccccc";

vi.mock("next/navigation", () => ({
  useParams: () => ({ uid: PERSON_UID }),
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
      id: PERSON_UID,
      display_name: "Aram Torosyan",
      email: "aram@example.com",
      phone: "+1 (916) 555-0188",
      has_lead: false,
      has_consultation: true,
      last_activity_at: "2026-05-04T18:32:00.000Z",
      source_providers: ["carestack"],
    },
    source_links: [
      {
        provider: "carestack",
        external_id: "1461274",
        entity: "Patient",
        confidence: 1.0,
        first_seen_at: "2026-05-01T09:30:00.000Z",
      },
    ],
    lead: null,
    consultations: [],
    timeline: [],
    financial_summary: null,
    carestack_origin: [],
    household_members: [],
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

describe("CareStack identity card on PersonDetailPage (ENG-308)", () => {
  it('renames "Patient since" to "First ingest" and exposes its info toggle', async () => {
    const detail = basePersonDetail({
      carestack_origin: [
        {
          patient_id: "1461274",
          earliest_activity_at: "2026-03-12T23:47:38.000Z",
          latest_activity_at: "2026-05-04T18:32:00.000Z",
          default_location_id: 10001,
          default_location_name: "Fusion El Dorado Hills",
          default_provider_id: 17,
          default_provider_name: "Dr Aram Torosyan",
          city: "El Dorado Hills",
          state: "CA",
        },
      ],
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Aram Torosyan")).toBeInTheDocument(),
    );

    // The legacy "Patient since" label MUST be gone — operators were
    // misreading it as a CareStack-side fact.
    expect(screen.queryByText("Patient since")).not.toBeInTheDocument();
    expect(screen.getByText("First ingest")).toBeInTheDocument();

    // The "?" toggle reveals the disambiguation copy.
    const toggle = screen.getByRole("button", { name: "What is First ingest?" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.queryByText(/Actual creation in CareStack may be earlier/i),
    ).not.toBeInTheDocument();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByText(/Actual creation in CareStack may be earlier/i),
    ).toBeInTheDocument();
  });

  it("renders Earliest activity as relative time when present", async () => {
    const detail = basePersonDetail({
      carestack_origin: [
        {
          patient_id: "1461274",
          earliest_activity_at: "2026-03-12T23:47:38.000Z",
          latest_activity_at: "2026-05-04T18:32:00.000Z",
          default_location_id: null,
          default_location_name: null,
          default_provider_id: null,
          default_provider_name: null,
          city: null,
          state: null,
        },
      ],
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });

    await waitFor(() => expect(screen.getByText("Earliest activity")).toBeInTheDocument());
    // formatRelative returns a non-empty string for any past datetime —
    // the row's value cell must NOT be "—".
    const row = screen.getByText("Earliest activity").parentElement;
    expect(row).not.toBeNull();
    expect(row?.textContent ?? "").not.toMatch(/Earliest activity\s*—\s*$/);
  });

  it('renders Earliest activity as "—" when no activity has been captured', async () => {
    const detail = basePersonDetail({
      carestack_origin: [
        {
          patient_id: "1461274",
          earliest_activity_at: null,
          latest_activity_at: null,
          default_location_id: null,
          default_location_name: null,
          default_provider_id: null,
          default_provider_name: null,
          city: null,
          state: null,
        },
      ],
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });

    await waitFor(() => expect(screen.getByText("Earliest activity")).toBeInTheDocument());
    const row = screen.getByText("Earliest activity").parentElement;
    expect(row?.textContent ?? "").toContain("—");
  });

  it("renders City, State under the card header when present", async () => {
    const detail = basePersonDetail({
      carestack_origin: [
        {
          patient_id: "1461274",
          earliest_activity_at: null,
          latest_activity_at: null,
          default_location_id: null,
          default_location_name: null,
          default_provider_id: null,
          default_provider_name: null,
          city: "El Dorado Hills",
          state: "CA",
        },
      ],
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("El Dorado Hills, CA")).toBeInTheDocument(),
    );
  });

  it("hides the city/state line when both are absent", async () => {
    const detail = basePersonDetail({
      carestack_origin: [
        {
          patient_id: "1461274",
          earliest_activity_at: null,
          latest_activity_at: null,
          default_location_id: null,
          default_location_name: null,
          default_provider_id: null,
          default_provider_name: null,
          city: null,
          state: null,
        },
      ],
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Aram Torosyan")).toBeInTheDocument(),
    );

    // No "Roseville", "El Dorado Hills", or trailing ", CA" — the line
    // is gone entirely. We assert nothing matches the comma-with-state
    // shape in the document.
    expect(screen.queryByText(/, CA$/)).not.toBeInTheDocument();
  });

  it('renders the resolved provider name when set; "—" otherwise', async () => {
    const detailResolved = basePersonDetail({
      carestack_origin: [
        {
          patient_id: "1461274",
          earliest_activity_at: null,
          latest_activity_at: null,
          default_location_id: null,
          default_location_name: null,
          default_provider_id: 17,
          default_provider_name: "Dr Aram Torosyan",
          city: null,
          state: null,
        },
      ],
    });
    installFetchSpy(defaultRouter(detailResolved));

    const { unmount } = render(<PersonDetailPage />, { wrapper });
    await waitFor(() =>
      expect(screen.getByText("Dr Aram Torosyan")).toBeInTheDocument(),
    );
    unmount();
    vi.unstubAllGlobals();

    // Unresolved → "—" in the Provider row.
    const detailUnresolved = basePersonDetail({
      carestack_origin: [
        {
          patient_id: "1461274",
          earliest_activity_at: null,
          latest_activity_at: null,
          default_location_id: null,
          default_location_name: null,
          default_provider_id: null,
          default_provider_name: null,
          city: null,
          state: null,
        },
      ],
    });
    installFetchSpy(defaultRouter(detailUnresolved));
    render(<PersonDetailPage />, { wrapper });
    await waitFor(() => expect(screen.getByText("Provider")).toBeInTheDocument());
    const row = screen.getByText("Provider").parentElement;
    expect(row?.textContent ?? "").toContain("—");
    expect(screen.queryByText("Dr Aram Torosyan")).not.toBeInTheDocument();
  });

  it("hides the multi-link banner when only one CareStack link exists", async () => {
    const detail = basePersonDetail({
      carestack_origin: [
        {
          patient_id: "1461274",
          earliest_activity_at: null,
          latest_activity_at: null,
          default_location_id: null,
          default_location_name: null,
          default_provider_id: null,
          default_provider_name: null,
          city: null,
          state: null,
        },
      ],
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });
    await waitFor(() => expect(screen.getByText("Earliest activity")).toBeInTheDocument());
    expect(
      screen.queryByText(/Linked to \d+ CareStack patient records/),
    ).not.toBeInTheDocument();
  });

  it("shows + expands the multi-link banner when 3 CareStack links exist", async () => {
    const detail = basePersonDetail({
      source_links: [
        {
          provider: "carestack",
          external_id: "1460847",
          entity: "Patient",
          confidence: 1.0,
        },
        {
          provider: "carestack",
          external_id: "1461274",
          entity: "Patient",
          confidence: 1.0,
        },
        {
          provider: "carestack",
          external_id: "2171827",
          entity: "Patient",
          confidence: 1.0,
        },
      ],
      carestack_origin: [
        {
          patient_id: "1460847",
          earliest_activity_at: "2025-11-04T10:00:00.000Z",
          latest_activity_at: "2026-02-18T09:15:00.000Z",
          default_location_id: 10001,
          default_location_name: "Fusion Roseville",
          default_provider_id: 17,
          default_provider_name: "Dr Aram Torosyan",
          city: "Roseville",
          state: "CA",
        },
        {
          patient_id: "1461274",
          earliest_activity_at: "2026-03-12T23:47:38.000Z",
          latest_activity_at: "2026-05-04T18:32:00.000Z",
          default_location_id: 10002,
          default_location_name: "Fusion El Dorado Hills",
          default_provider_id: null,
          default_provider_name: null,
          city: "El Dorado Hills",
          state: "CA",
        },
        {
          patient_id: "2171827",
          earliest_activity_at: null,
          latest_activity_at: null,
          default_location_id: null,
          default_location_name: null,
          default_provider_id: null,
          default_provider_name: null,
          city: null,
          state: null,
        },
      ],
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });
    await waitFor(() =>
      expect(
        screen.getByText("Linked to 3 CareStack patient records"),
      ).toBeInTheDocument(),
    );

    const banner = screen.getByRole("button", {
      name: /Linked to 3 CareStack patient records/,
    });
    expect(banner).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(banner);
    expect(banner).toHaveAttribute("aria-expanded", "true");

    // Each pid shows on its own row in the expander.
    expect(screen.getByText("1460847")).toBeInTheDocument();
    expect(screen.getByText("1461274")).toBeInTheDocument();
    expect(screen.getByText("2171827")).toBeInTheDocument();
    // Resolved location name visible.
    expect(screen.getByText("Fusion Roseville")).toBeInTheDocument();
    // Resolved provider visible. (Dr Aram Torosyan may show up in two
    // places — the primary card AND the expander; we just check it's
    // there.)
    const drCells = screen.getAllByText("Dr Aram Torosyan");
    expect(drCells.length).toBeGreaterThanOrEqual(1);
  });
});

describe("Per-pid names + patient details panel (ENG-310 A + B)", () => {
  it('renders "First Last · pid" in the multi-link expander row', async () => {
    const detail = basePersonDetail({
      source_links: [
        {
          provider: "carestack",
          external_id: "1460847",
          entity: "Patient",
          confidence: 1.0,
        },
        {
          provider: "carestack",
          external_id: "2171827",
          entity: "Patient",
          confidence: 1.0,
        },
      ],
      carestack_origin: [
        {
          patient_id: "1460847",
          earliest_activity_at: null,
          latest_activity_at: null,
          default_location_id: null,
          default_location_name: null,
          default_provider_id: null,
          default_provider_name: null,
          city: null,
          state: null,
          first_name: "Gaiane",
          last_name: "Torosyan",
        },
        {
          patient_id: "2171827",
          earliest_activity_at: null,
          latest_activity_at: null,
          default_location_id: null,
          default_location_name: null,
          default_provider_id: null,
          default_provider_name: null,
          city: null,
          state: null,
          first_name: "Eduard",
          last_name: "Torosyan",
        },
      ],
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });
    await waitFor(() =>
      expect(
        screen.getByText("Linked to 2 CareStack patient records"),
      ).toBeInTheDocument(),
    );
    fireEvent.click(
      screen.getByRole("button", { name: /Linked to 2 CareStack patient records/ }),
    );
    expect(screen.getByText("Gaiane Torosyan · 1460847")).toBeInTheDocument();
    expect(screen.getByText("Eduard Torosyan · 2171827")).toBeInTheDocument();
  });

  it('falls back to bare pid when names are null', async () => {
    const detail = basePersonDetail({
      source_links: [
        {
          provider: "carestack",
          external_id: "1460847",
          entity: "Patient",
          confidence: 1.0,
        },
        {
          provider: "carestack",
          external_id: "2171827",
          entity: "Patient",
          confidence: 1.0,
        },
      ],
      carestack_origin: [
        {
          patient_id: "1460847",
          earliest_activity_at: null,
          latest_activity_at: null,
          default_location_id: null,
          default_location_name: null,
          default_provider_id: null,
          default_provider_name: null,
          city: null,
          state: null,
          first_name: null,
          last_name: null,
        },
        {
          patient_id: "2171827",
          earliest_activity_at: null,
          latest_activity_at: null,
          default_location_id: null,
          default_location_name: null,
          default_provider_id: null,
          default_provider_name: null,
          city: null,
          state: null,
          first_name: null,
          last_name: null,
        },
      ],
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });
    await waitFor(() =>
      expect(
        screen.getByText("Linked to 2 CareStack patient records"),
      ).toBeInTheDocument(),
    );
    fireEvent.click(
      screen.getByRole("button", { name: /Linked to 2 CareStack patient records/ }),
    );
    expect(screen.getByText("1460847")).toBeInTheDocument();
    expect(screen.getByText("2171827")).toBeInTheDocument();
    // Bare-pid rows render the pid as its own text node — no "Name · pid"
    // prefix. (A "·" does appear in the card header's "email · phone"
    // description, so we scope the negative check to the name-pid pattern.)
    expect(screen.queryByText(/· 1460847/)).not.toBeInTheDocument();
    expect(screen.queryByText(/· 2171827/)).not.toBeInTheDocument();
  });

  it("Patient details panel is hidden by default and toggles on click", async () => {
    const detail = basePersonDetail({
      source_links: [
        {
          provider: "carestack",
          external_id: "1460847",
          entity: "Patient",
          confidence: 1.0,
        },
        {
          provider: "carestack",
          external_id: "1461274",
          entity: "Patient",
          confidence: 1.0,
        },
      ],
      carestack_origin: [
        {
          patient_id: "1460847",
          earliest_activity_at: null,
          latest_activity_at: null,
          default_location_id: null,
          default_location_name: null,
          default_provider_id: null,
          default_provider_name: null,
          city: null,
          state: null,
          first_name: "Gaiane",
          last_name: "Torosyan",
          dob: "1985-04-12",
          gender: "Female",
          marital_status: "Married",
          mobile: "+1 (916) 215-4258",
          phone_with_ext: null,
          work_phone_with_ext: null,
          email: "gaiane@example.com",
          address_line1: "1 Oak St",
          address_line2: null,
          address_zip: "95762",
          patient_identifier: "MRN-1460847",
          account_id: "10762",
        },
        {
          patient_id: "1461274",
          earliest_activity_at: null,
          latest_activity_at: null,
          default_location_id: null,
          default_location_name: null,
          default_provider_id: null,
          default_provider_name: null,
          city: null,
          state: null,
          first_name: "Gaiane",
          last_name: "Torosyan",
        },
      ],
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });
    await waitFor(() =>
      expect(
        screen.getByText("Linked to 2 CareStack patient records"),
      ).toBeInTheDocument(),
    );
    // Open the multi-link expander first.
    fireEvent.click(
      screen.getByRole("button", { name: /Linked to 2 CareStack patient records/ }),
    );

    // DOB is NOT visible until the per-pid Patient details panel is opened.
    expect(screen.queryByText("1985-04-12")).not.toBeInTheDocument();

    // Click the first Patient details toggle.
    const toggles = screen.getAllByRole("button", { name: /Patient details/i });
    expect(toggles.length).toBeGreaterThanOrEqual(2);
    expect(toggles[0]).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggles[0]!);
    expect(toggles[0]).toHaveAttribute("aria-expanded", "true");

    // DOB, gender, mobile, email, address, identifiers now visible.
    expect(screen.getByText("1985-04-12")).toBeInTheDocument();
    expect(screen.getByText("Female")).toBeInTheDocument();
    expect(screen.getByText("Married")).toBeInTheDocument();
    expect(screen.getByText("+1 (916) 215-4258")).toBeInTheDocument();
    expect(screen.getByText("gaiane@example.com")).toBeInTheDocument();
    expect(screen.getByText(/1 Oak St/)).toBeInTheDocument();
    expect(screen.getByText("MRN-1460847")).toBeInTheDocument();
    expect(screen.getByText("10762")).toBeInTheDocument();
  });

  it('Patient details panel renders "—" for absent fields', async () => {
    const detail = basePersonDetail({
      source_links: [
        {
          provider: "carestack",
          external_id: "1460847",
          entity: "Patient",
          confidence: 1.0,
        },
        {
          provider: "carestack",
          external_id: "1461274",
          entity: "Patient",
          confidence: 1.0,
        },
      ],
      carestack_origin: [
        {
          patient_id: "1460847",
          earliest_activity_at: null,
          latest_activity_at: null,
          default_location_id: null,
          default_location_name: null,
          default_provider_id: null,
          default_provider_name: null,
          city: null,
          state: null,
        },
        {
          patient_id: "1461274",
          earliest_activity_at: null,
          latest_activity_at: null,
          default_location_id: null,
          default_location_name: null,
          default_provider_id: null,
          default_provider_name: null,
          city: null,
          state: null,
        },
      ],
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });
    await waitFor(() =>
      expect(
        screen.getByText("Linked to 2 CareStack patient records"),
      ).toBeInTheDocument(),
    );
    fireEvent.click(
      screen.getByRole("button", { name: /Linked to 2 CareStack patient records/ }),
    );
    const toggles = screen.getAllByRole("button", { name: /Patient details/i });
    fireEvent.click(toggles[0]!);
    // The opened panel must contain at least one "—" placeholder for
    // an absent field (e.g. DOB).
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});

describe("Household / shared contact card (ENG-310 C)", () => {
  it("hides the card entirely when there are no household members", async () => {
    const detail = basePersonDetail({ household_members: [] });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });
    await waitFor(() =>
      expect(screen.getByText("Aram Torosyan")).toBeInTheDocument(),
    );
    expect(
      screen.queryByText(/Household \/ shared contact/i),
    ).not.toBeInTheDocument();
  });

  it("renders members with navigational link + masked hint + disclaimer copy", async () => {
    const SIBLING_A = "66666666-bbbb-4444-cccc-dddddddddddd";
    const SIBLING_B = "77777777-cccc-4444-dddd-eeeeeeeeeeee";
    const detail = basePersonDetail({
      household_members: [
        {
          person_uid: SIBLING_A,
          display_name: "Anush Torosyan",
          shared_via: "phone",
          shared_value_masked: "···4258",
        },
        {
          person_uid: SIBLING_B,
          display_name: "Karen Torosyan",
          shared_via: "both",
          shared_value_masked: "···4258",
        },
      ],
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });
    await waitFor(() =>
      expect(screen.getByText("Household / shared contact")).toBeInTheDocument(),
    );

    // Disclaimer copy: links are shown explicitly so the same person
    // across multiple records is visible inline, not hidden behind a
    // navigational click.
    expect(
      screen.getByText(
        /Linked by shared phone or email\. Same person across multiple records appears here/i,
      ),
    ).toBeInTheDocument();

    // Anush row: working Link with masked hint.
    const anushLink = screen.getByRole("link", { name: "Anush Torosyan" });
    expect(anushLink).toHaveAttribute("href", `/persons/${SIBLING_A}`);
    expect(
      screen.getByText(/Same phone — not merged:.*···4258/i),
    ).toBeInTheDocument();

    // Karen row: shared via "both".
    const karenLink = screen.getByRole("link", { name: "Karen Torosyan" });
    expect(karenLink).toHaveAttribute("href", `/persons/${SIBLING_B}`);
    expect(
      screen.getByText(/Same phone & email — not merged:.*···4258/i),
    ).toBeInTheDocument();
  });

  it("renders inline consultations + balance for each household member", async () => {
    const SIBLING = "88888888-aaaa-4444-bbbb-cccccccccccc";
    const detail = basePersonDetail({
      household_members: [
        {
          person_uid: SIBLING,
          display_name: "Karen Torosyan",
          shared_via: "phone",
          shared_value_masked: "···4258",
        },
      ],
      consultations: [
        {
          id: "11111111-1111-4111-8111-111111111111",
          status: "scheduled",
          scheduled_at: "2026-06-10T14:00:00.000Z",
          provider: "carestack",
        },
        {
          id: "22222222-2222-4222-8222-222222222222",
          status: "completed",
          scheduled_at: "2026-05-01T14:00:00.000Z",
          provider: "carestack",
        },
      ],
      financial_summary: {
        billed: 1200,
        adjustments: 0,
        paid: 800,
        balance: 400,
        snapshot_received_at: "2026-06-01T00:00:00.000Z",
        carestack_patient_ids: ["1461274"],
        patient_count: 1,
      },
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });
    await waitFor(() =>
      expect(
        screen.getByText("Household / shared contact"),
      ).toBeInTheDocument(),
    );

    // The member row shows the fetched person's consultation breakdown
    // and balance inline. defaultRouter returns the same detail for any
    // /api/persons/<uid> call so the sibling fetch hydrates with the
    // same fixture (1 scheduled + 1 completed; balance $400.00).
    await waitFor(() =>
      expect(
        screen.getByText(
          /2 · 1 scheduled · 1 completed/i,
        ),
      ).toBeInTheDocument(),
    );
    // Two $400.00 — one in the main FinancialSummaryCard for Aram, one
    // inline on the household member row (defaultRouter returns the
    // same detail fixture for any /api/persons/<uid> call).
    expect(screen.getAllByText(/\$400\.00/).length).toBeGreaterThanOrEqual(2);
  });

  it("falls back to the person uid when display_name is null", async () => {
    const SIBLING = "66666666-bbbb-4444-cccc-dddddddddddd";
    const detail = basePersonDetail({
      household_members: [
        {
          person_uid: SIBLING,
          display_name: null,
          shared_via: "email",
          shared_value_masked: "g···@example.com",
        },
      ],
    });
    installFetchSpy(defaultRouter(detail));

    render(<PersonDetailPage />, { wrapper });
    await waitFor(() =>
      expect(screen.getByText("Household / shared contact")).toBeInTheDocument(),
    );
    expect(screen.getByRole("link", { name: SIBLING })).toHaveAttribute(
      "href",
      `/persons/${SIBLING}`,
    );
    expect(
      screen.getByText(/Same email — not merged:.*g···@example\.com/i),
    ).toBeInTheDocument();
  });
});

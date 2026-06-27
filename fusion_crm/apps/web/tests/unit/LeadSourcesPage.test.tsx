import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import LeadSourcesPage from "@/app/(staff)/dev/lead-sources/page";

const PERSON = "aaaa1111-1111-1111-1111-111111111111";
const LEAD = "ffff0000-0000-0000-0000-000000000001";

const TREE = {
  total_leads: 57,
  consults_scheduled: 10,
  consults_attended: 4,
  collected_amount: 25400,
  sources: [
    {
      key: "unknown",
      label: "unknown",
      level: "channel",
      leads: 40,
      consults_scheduled: 6,
      consults_attended: 0,
      collected_amount: 0,
      children: [],
    },
    {
      key: "google",
      label: "google",
      level: "channel",
      leads: 17,
      consults_scheduled: 4,
      consults_attended: 4,
      collected_amount: 25400,
      children: [
        {
          key: "google/Google Ads",
          label: "Google Ads",
          level: "source",
          leads: 15,
          consults_scheduled: 4,
          consults_attended: 4,
          collected_amount: 25400,
          children: [],
        },
      ],
    },
  ],
};

const LEADS = {
  total: 1,
  items: [
    {
      id: LEAD,
      person_uid: PERSON,
      display_name: "Jane Implant",
      email: "jane@example.com",
      phone: "+19165550100",
      collected_amount: 2500,
      assigned_center: "El Dorado Hills",
      location_mismatch: false,
      status: "new",
      source_label: "Google Ads",
      utm_medium: "cpc",
      utm_campaign: "implants-q2",
      created_at: "2026-05-02T00:00:00+00:00",
      provider_created_at: "2026-05-01T10:30:00+00:00",
      attribution: { gclid: "abc123" },
    },
  ],
};

function installFetchSpy(): Array<string> {
  const log: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      log.push(url);
      if (url.includes("/lead-sources/tree")) {
        return new Response(JSON.stringify(TREE), { status: 200 });
      }
      if (url.includes("/lead-sources/leads")) {
        return new Response(JSON.stringify(LEADS), { status: 200 });
      }
      return new Response(JSON.stringify({ error: { code: "NOT_FOUND", message: "nope", details: {} } }), {
        status: 404,
      });
    }),
  );
  return log;
}

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("LeadSourcesPage", () => {
  it("renders the source tree with funnel counts", async () => {
    installFetchSpy();
    render(<LeadSourcesPage />, { wrapper });

    expect(await screen.findByText("google")).toBeInTheDocument();
    expect(screen.getByText("unknown")).toBeInTheDocument();
    // Totals strip (leads + collected money).
    expect(screen.getByText("57")).toBeInTheDocument();
    expect(screen.getAllByText("$25,400").length).toBeGreaterThan(0);
    // Source level is collapsed until the channel is expanded.
    expect(screen.queryByText("Google Ads")).not.toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Expand google"));
    expect(await screen.findByText("Google Ads")).toBeInTheDocument();
  });

  it("opens the drill-down dialog with the lead list", async () => {
    const log = installFetchSpy();
    render(<LeadSourcesPage />, { wrapper });

    await userEvent.click(await screen.findByText("google"));

    expect(await screen.findByText("1 lead in this bucket")).toBeInTheDocument();
    expect(screen.getByText("new")).toBeInTheDocument();
    expect(screen.getByText("Jane Implant")).toBeInTheDocument();
    expect(screen.getByText("+19165550100")).toBeInTheDocument();
    expect(screen.getByText("$2,500")).toBeInTheDocument();
    expect(screen.getByText("implants-q2")).toBeInTheDocument();

    await waitFor(() =>
      expect(
        log.some((url) =>
          url.includes("/lead-sources/leads") && url.includes("channel=google"),
        ),
      ).toBe(true),
    );
  });
});

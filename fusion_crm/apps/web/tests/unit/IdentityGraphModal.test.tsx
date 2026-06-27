import React from "react";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { IdentityGraphModal } from "@/components/person/IdentityGraphModal";
import type { PersonDetail } from "@/lib/api/schemas";

const DETAIL: PersonDetail = {
  summary: {
    id: "11111111-1111-1111-1111-111111111111",
    display_name: "Alice Morgan",
    email: "alice@example.com",
    phone: "+1 555-0142",
    has_lead: true,
    has_consultation: true,
    last_activity_at: "2026-05-04T18:32:00.000Z",
    source_providers: ["salesforce", "carestack"],
  },
  lead: null,
  consultations: [],
  source_links: [
    {
      provider: "salesforce",
      external_id: "00Q5j000001abcd",
      entity: "Lead",
      confidence: 0.98,
    },
    {
      provider: "carestack",
      external_id: "PT-9985",
      entity: "Patient",
      confidence: 0.92,
    },
  ],
  timeline: [],
  carestack_origin: [],
  household_members: [],
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("IdentityGraphModal", () => {
  it("renders the person's display name in the title when open", () => {
    render(
      <IdentityGraphModal
        open={true}
        onOpenChange={vi.fn()}
        detail={DETAIL}
      />,
    );
    // Radix Dialog Title carries the heading text — assert via accessible name.
    expect(
      screen.getByText(/Identity graph — Alice Morgan/i),
    ).toBeInTheDocument();
  });

  it("hides the title when open=false", () => {
    render(
      <IdentityGraphModal
        open={false}
        onOpenChange={vi.fn()}
        detail={DETAIL}
      />,
    );
    expect(
      screen.queryByText(/Identity graph — Alice Morgan/i),
    ).not.toBeInTheDocument();
  });

  it("includes the confidence-tier description", () => {
    render(
      <IdentityGraphModal
        open={true}
        onOpenChange={vi.fn()}
        detail={DETAIL}
      />,
    );
    expect(screen.getByText(/source links/i)).toBeInTheDocument();
  });
});

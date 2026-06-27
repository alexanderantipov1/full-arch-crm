// Source-attribution page documentation — the staff-facing explanation of the
// vendor-attribution workflow (ENG-569): what a vendor is, how to distribute
// traffic, how monthly cost and cost-per-lead are computed, and how the month
// filter works. Rendered in a popup on /project-manager/attribution.
//
// Reuses the DocSection/DocTable shape from paymentsDoc so the renderer is
// shared. English-only for now; add a ru variant later if needed.

import type { DocSection } from "@/lib/docs/paymentsDoc";

export type AttributionDocContent = {
  title: string;
  subtitle: string;
  sections: DocSection[];
};

export const attributionDoc: AttributionDocContent = {
  title: "Source attribution — how to use this page",
  subtitle:
    "Attribute every lead to a vendor (an agency or your in-house team), distribute the unassigned traffic, set what each vendor costs per month, and read the cost per lead.",
  sections: [
    {
      heading: "1. What this page shows",
      paragraphs: [
        "Each lead's resolved origin as a distribution chain: Vendor → Channel → Campaign, with funnel counts (leads, consultations scheduled and attended, collected revenue) at every level.",
        "A vendor is WHO manages the traffic — an external agency, or your own in-house marketing team (the in-house team is a vendor too). Channel and campaign are WHERE the traffic comes from. The same channel (e.g. Facebook) can belong to different vendors.",
        "Click any row to inspect the individual leads behind it.",
      ],
    },
    {
      heading: "2. Add your vendors",
      paragraphs: [
        "Open Settings → Vendors. Create one vendor per agency, plus one for your in-house team (kind = In-house). Give each a colour so it stands out in the tree.",
      ],
      bullets: [
        "Anything not bound to a vendor stays Unassigned — it is never silently counted as in-house.",
        "Deactivating a vendor hides it from new binding without deleting its history.",
      ],
    },
    {
      heading: "3. Distribute traffic to vendors",
      paragraphs: [
        "In Settings → Vendors, edit a vendor and open \"Bind unassigned traffic\". The system lists the real traffic signatures behind the Unassigned leads (e.g. utm_source = Facebook → 244 leads) with their lead counts.",
        "Pick a signature and click Attach — every lead matching it now resolves to that vendor, and the Unassigned bucket shrinks. The \"Distribute\" link in this page's header jumps straight there.",
      ],
      bullets: [
        "Suggested for {vendor}: the system proposes signatures whose value matches the vendor's name (e.g. \"Dima …\" campaigns for vendor Dima). Click Accept to bind — the agent proposes, you confirm. Nothing is bound automatically.",
        "Bindings are rules: they also apply to future leads, not just today's.",
      ],
    },
    {
      heading: "4. Set monthly spend",
      paragraphs: [
        "On a vendor's card, set what you pay it per month. Two modes:",
      ],
      bullets: [
        "Same amount every month (default) — one flat monthly fee (e.g. a retainer). Set it once.",
        "Different per month — turn the flag off and enter each month's amount separately.",
        "The in-house team's budget is entered the same way — it is a vendor.",
      ],
    },
    {
      heading: "5. Read the month + cost per lead",
      paragraphs: [
        "Pick a month at the top of the page to scope the whole tree to that month's leads; \"all time\" clears it.",
        "When a month is selected, each vendor row shows a Cost / CPL column.",
      ],
      formula: "Cost per lead (CPL) = vendor's fee for the month ÷ that vendor's leads in the month",
      bullets: [
        "A vendor with no fee set for the month shows \"—\", not 0.",
        "Use CPL to compare agencies against each other and against in-house, and to decide where to spend more or less.",
      ],
    },
    {
      heading: "6. Unassigned & needs review",
      paragraphs: [
        "\"Need review\" (top-right badge) is the count of leads the resolver could not place at all — the gap to drive toward zero by improving ingestion.",
        "Unassigned is traffic that resolved to a channel but no vendor yet — close it with the binding workflow in step 3.",
      ],
    },
    {
      heading: "Not yet available (coming next)",
      bullets: [
        "Automatic ad-spend from Google / Meta / TikTok (today the monthly amount is entered by hand).",
        "Cost per attended consult / per collected revenue (today CPL is per lead).",
        "AI-written binding suggestions (today the suggester matches on the vendor's name).",
      ],
    },
  ],
};

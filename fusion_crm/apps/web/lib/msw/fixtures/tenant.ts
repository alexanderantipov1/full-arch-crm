import type { TenantWithRelations } from "@/lib/api/schemas";

/**
 * Single-tenant fixture mirroring the operator's real Fusion Dental Implants
 * footprint (4 CareStack locations + SF/CS/voice/AI/SMS credentials). Used
 * by the MSW handler for `GET /api/tenant/current` until the FastAPI route
 * lands.
 *
 * Dates below are deterministic — no `new Date()` so the fixture stays
 * stable across renders. `last_refreshed_at` values land within the past
 * 24h so `formatRelative` shows a sensible "Xh ago" reading.
 *
 * ENG-135 extends the integrations list with one Google Workspace mailbox
 * (default) + one Microsoft 365 mailbox so the outreach mailbox picker has
 * something to render in dev.
 */

const NOW_MINUS_30M = "2026-05-09T17:30:00Z";
const NOW_MINUS_2H = "2026-05-09T16:00:00Z";
const NOW_MINUS_1H = "2026-05-09T17:00:00Z";
const NOW_MINUS_45M = "2026-05-09T17:15:00Z";
const NOW_MINUS_3H = "2026-05-09T15:00:00Z";
const NOW_MINUS_4H = "2026-05-09T14:00:00Z";
const NOW_MINUS_6H = "2026-05-09T12:00:00Z";
const FUTURE_30D = "2026-06-08T18:00:00Z";

export const tenantFixture: TenantWithRelations = {
  tenant: {
    id: "11111111-1111-1111-1111-111111111111",
    slug: "fusion-dental-implants",
    name: "Fusion Dental Implants",
    primary_email: "info@fusiondentalimplants.com",
    primary_phone: "(530) 556-4810",
    website: "https://www.fusiondentalimplants.com",
    logo_url: null,
    billing_email: null,
    industry: "dental_implants",
    tax_id: null,
    timezone: "America/Los_Angeles",
    locale: "en-US",
    status: "active",
    subscription_status: "trial",
    created_at: "2026-04-23T01:26:24Z",
  },
  locations: [
    {
      id: "22222222-0000-0000-0000-000000000001",
      external_ref: { carestack_location_id: 1 },
      name: "Fusion Dental Implants",
      short_name: "FUSION-EDH",
      address_line1: "4913 Golden Foothill Pkwy",
      address_line2: null,
      city: "El Dorado Hills",
      state: "CA",
      zip: "95762-9632",
      country: "US",
      phone: "(530) 556-4810",
      timezone_override: null,
      latitude: 38.6355327,
      longitude: -121.0685431,
      is_active: true,
    },
    {
      id: "22222222-0000-0000-0000-000000000002",
      external_ref: { carestack_location_id: 8027 },
      name: "Fusion Dental Implants — Roseville",
      short_name: "FUSION-ROS",
      address_line1: "911 Reserve Drive, Suite 150",
      address_line2: null,
      city: "Roseville",
      state: "CA",
      zip: "95678-1383",
      country: "US",
      phone: "(916) 783-2110",
      timezone_override: null,
      latitude: null,
      longitude: null,
      is_active: true,
    },
    {
      id: "22222222-0000-0000-0000-000000000003",
      external_ref: { carestack_location_id: 9028 },
      name: "Cosmo Dental",
      short_name: "COSMO",
      address_line1: "490 Post Street",
      address_line2: "Suite 1022",
      city: "San Francisco",
      state: "CA",
      zip: "94102-1301",
      country: "US",
      phone: "(415) 800-7594",
      timezone_override: null,
      latitude: null,
      longitude: null,
      is_active: true,
    },
    {
      id: "22222222-0000-0000-0000-000000000004",
      external_ref: { carestack_location_id: 10029 },
      name: "Galleria Oral Surgery & Dental Implants",
      short_name: "GALLERIA",
      address_line1: "911 Reserve Drive, Suite 150",
      address_line2: null,
      city: "Roseville",
      state: "CA",
      zip: "95678-1383",
      country: "US",
      phone: "(916) 783-2110",
      timezone_override: null,
      latitude: null,
      longitude: null,
      is_active: true,
    },
  ],
  integrations: [
    {
      id: "33333333-0000-0000-0000-000000000001",
      provider_kind: "salesforce",
      credential_kind: "oauth_token",
      display_name: "Salesforce production org",
      status: "active",
      expires_at: FUTURE_30D,
      last_refreshed_at: NOW_MINUS_1H,
      mailbox_email: null,
      location_id: null,
      is_default: true,
      tags: [],
    },
    {
      id: "33333333-0000-0000-0000-000000000002",
      provider_kind: "carestack",
      credential_kind: "password_grant",
      display_name: "CareStack — Antipov account",
      status: "active",
      expires_at: null,
      last_refreshed_at: NOW_MINUS_2H,
      mailbox_email: null,
      location_id: null,
      is_default: true,
      tags: [],
    },
    {
      id: "33333333-0000-0000-0000-000000000003",
      provider_kind: "vapi",
      credential_kind: "api_key",
      display_name: "VAPI — voice agent platform",
      status: "active",
      expires_at: null,
      last_refreshed_at: NOW_MINUS_30M,
      mailbox_email: null,
      location_id: null,
      is_default: true,
      tags: [],
    },
    {
      id: "33333333-0000-0000-0000-000000000004",
      provider_kind: "openai",
      credential_kind: "api_key",
      display_name: "OpenAI — GPT models",
      status: "active",
      expires_at: null,
      last_refreshed_at: NOW_MINUS_45M,
      mailbox_email: null,
      location_id: null,
      is_default: true,
      tags: [],
    },
    {
      id: "33333333-0000-0000-0000-000000000005",
      provider_kind: "twilio",
      credential_kind: "api_key",
      display_name: "Twilio — SMS + voice transport",
      status: "active",
      expires_at: null,
      last_refreshed_at: NOW_MINUS_3H,
      mailbox_email: null,
      location_id: null,
      is_default: true,
      tags: [],
    },
    {
      id: "33333333-0000-0000-0000-000000000006",
      provider_kind: "google_workspace",
      credential_kind: "oauth_token",
      display_name: "marketing@fusion-dental.com",
      status: "active",
      expires_at: FUTURE_30D,
      last_refreshed_at: NOW_MINUS_4H,
      mailbox_email: "marketing@fusion-dental.com",
      location_id: "22222222-0000-0000-0000-000000000001",
      is_default: true,
      tags: ["marketing", "welcome"],
    },
    {
      id: "33333333-0000-0000-0000-000000000007",
      provider_kind: "microsoft_365",
      credential_kind: "oauth_token",
      display_name: "office@galleria-oral.com",
      status: "active",
      expires_at: FUTURE_30D,
      last_refreshed_at: NOW_MINUS_6H,
      mailbox_email: "office@galleria-oral.com",
      location_id: "22222222-0000-0000-0000-000000000004",
      is_default: true,
      tags: ["operational", "reminders"],
    },
  ],
  settings: [
    {
      key: "provider_link_bases",
      value: {
        salesforce_lightning_base_url:
          "https://fusiondentalimplants.lightning.force.com",
        carestack_app_base_url: "https://antipov.carestack.com",
      },
      updated_at: NOW_MINUS_30M,
    },
  ],
};

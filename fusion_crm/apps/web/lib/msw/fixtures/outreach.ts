import type {
  CampaignOut,
  PersonPreviewOut,
  SendOut,
  SuppressionOut,
  TemplateOut,
} from "@/lib/api/schemas/outreach";

/**
 * Deterministic outreach fixtures used by the MSW handlers. The mutable
 * store stays in-memory only — restarting the dev server resets state.
 * Replace these handlers (and this file) with deletions once the FastAPI
 * outreach routes (ENG-133 follow-up PR) ship.
 */

const TENANT_ID = "11111111-1111-1111-1111-111111111111";
const NOW = () => new Date().toISOString();
const ISO = (iso: string) => iso;

export interface OutreachStore {
  templates: TemplateOut[];
  campaigns: CampaignOut[];
  sends: SendOut[];
  suppressions: SuppressionOut[];
}

function seedTemplates(): TemplateOut[] {
  return [
    {
      id: "aa000001-0000-0000-0000-000000000001",
      tenant_id: TENANT_ID,
      name: "Welcome to Fusion Dental",
      description: "Greets a brand-new lead the first time we email them.",
      subject_template: "Welcome, {{patient.first_name}} 👋",
      body_template:
        "Hi {{patient.first_name}},\n\n" +
        "Thanks for reaching out to {{tenant.name}}. We'll be in touch\n" +
        "shortly to book your consult.\n\n" +
        "— Fusion Dental",
      body_format: "markdown",
      category: "marketing",
      tracking_enabled: true,
      intent_tags: ["welcome", "first_touch"],
      version: 1,
      status: "active",
      created_by_actor_id: null,
      created_at: ISO("2026-05-01T15:00:00Z"),
      updated_at: ISO("2026-05-08T11:30:00Z"),
    },
    {
      id: "aa000001-0000-0000-0000-000000000002",
      tenant_id: TENANT_ID,
      name: "Appointment reminder — 24h",
      description: "Reminder sent the day before a booked consult.",
      subject_template:
        "Reminder: appointment {{appointment.date}} at {{appointment.time}}",
      body_template:
        "Hi {{patient.first_name}},\n\n" +
        "This is a friendly reminder that your consult at\n" +
        "{{location.name}} is on {{appointment.date}} at\n" +
        "{{appointment.time}}.\n\n" +
        "Reply STOP to cancel.",
      body_format: "markdown",
      category: "transactional",
      tracking_enabled: false,
      intent_tags: ["reminder"],
      version: 2,
      status: "active",
      created_by_actor_id: null,
      created_at: ISO("2026-04-20T15:00:00Z"),
      updated_at: ISO("2026-05-06T09:15:00Z"),
    },
  ];
}

function seedCampaigns(): CampaignOut[] {
  return [
    {
      id: "bb000002-0000-0000-0000-000000000001",
      tenant_id: TENANT_ID,
      template_id: "aa000001-0000-0000-0000-000000000001",
      name: "May welcome blast",
      recipient_query: { lead_status: "new", limit: 25 },
      mailbox_credential_id: "33333333-0000-0000-0000-000000000006",
      mailbox_strategy: "explicit",
      scheduled_for: ISO("2026-05-09T16:00:00Z"),
      sent_count: 18,
      opened_count: 7,
      bounced_count: 1,
      unsubscribed_count: 0,
      status: "sent",
      created_by_actor_id: null,
      created_at: ISO("2026-05-08T22:10:00Z"),
      updated_at: ISO("2026-05-09T16:14:00Z"),
    },
  ];
}

function seedSends(): SendOut[] {
  return [
    {
      id: "cc000003-0000-0000-0000-000000000001",
      tenant_id: TENANT_ID,
      campaign_id: "bb000002-0000-0000-0000-000000000001",
      person_uid: "dd000004-0000-0000-0000-000000000001",
      recipient_email: "jane.doe@example.com",
      message_id: "<msg-1@galleria.fusion>",
      mailbox_credential_id: "33333333-0000-0000-0000-000000000006",
      status: "sent",
      sent_at: ISO("2026-05-09T16:01:11Z"),
      error_text: null,
      created_at: ISO("2026-05-09T16:01:00Z"),
      updated_at: ISO("2026-05-09T16:01:11Z"),
    },
    {
      id: "cc000003-0000-0000-0000-000000000002",
      tenant_id: TENANT_ID,
      campaign_id: "bb000002-0000-0000-0000-000000000001",
      person_uid: "dd000004-0000-0000-0000-000000000002",
      recipient_email: "bob.smith@example.com",
      message_id: null,
      mailbox_credential_id: "33333333-0000-0000-0000-000000000006",
      status: "bounced",
      sent_at: null,
      error_text: "550 5.1.1 mailbox does not exist",
      created_at: ISO("2026-05-09T16:01:00Z"),
      updated_at: ISO("2026-05-09T16:01:30Z"),
    },
  ];
}

function seedSuppressions(): SuppressionOut[] {
  return [
    {
      tenant_id: TENANT_ID,
      recipient_email_normalised: "bob.smith@example.com",
      reason: "bounce_hard",
      source_send_id: "cc000003-0000-0000-0000-000000000002",
      created_at: ISO("2026-05-09T16:01:31Z"),
    },
  ];
}

export const outreachStore: OutreachStore = {
  templates: seedTemplates(),
  campaigns: seedCampaigns(),
  sends: seedSends(),
  suppressions: seedSuppressions(),
};

/** Tiny synthetic recipient pool used by the campaign preview endpoint. */
export const recipientPool: PersonPreviewOut[] = [
  {
    person_uid: "dd000004-0000-0000-0000-000000000001",
    display_name: "Jane Doe",
    primary_email: "jane.doe@example.com",
  },
  {
    person_uid: "dd000004-0000-0000-0000-000000000002",
    display_name: "Bob Smith",
    primary_email: "bob.smith@example.com",
  },
  {
    person_uid: "dd000004-0000-0000-0000-000000000003",
    display_name: "Carol Liu",
    primary_email: "carol.liu@example.com",
  },
  {
    person_uid: "dd000004-0000-0000-0000-000000000004",
    display_name: "Dan Park",
    primary_email: "dan.park@example.com",
  },
  {
    person_uid: "dd000004-0000-0000-0000-000000000005",
    display_name: "Erin O'Connell",
    primary_email: "erin.oconnell@example.com",
  },
];

export function newTemplateId(): string {
  return `aa000001-0000-0000-0000-${Math.floor(
    Math.random() * 1e12,
  )
    .toString(16)
    .padStart(12, "0")
    .slice(-12)}`;
}

export function newCampaignId(): string {
  return `bb000002-0000-0000-0000-${Math.floor(
    Math.random() * 1e12,
  )
    .toString(16)
    .padStart(12, "0")
    .slice(-12)}`;
}

export function nowIso(): string {
  return NOW();
}

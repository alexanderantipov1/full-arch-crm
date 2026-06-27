/**
 * Server-side mapping from Salesforce Lead rows to our wire format.
 * Stays in lockstep with `lib/api/schemas/person.ts`.
 */
import "server-only";
import crypto from "node:crypto";
import type {
  LeadStatus,
  PersonDetail,
  PersonSummary,
  TimelineEvent,
} from "@/lib/api/schemas";

export interface SFLead {
  Id: string;
  FirstName: string | null;
  LastName: string | null;
  Email: string | null;
  Phone: string | null;
  Status: string | null;
  LeadSource: string | null;
  CreatedDate: string;
  LastModifiedDate: string;
}

const NAMESPACE = "fusion-sf-lead";

/** Deterministic UUID-shaped string from an SF record Id. */
export function uuidFromSFId(sfId: string): string {
  const hash = crypto.createHash("sha1").update(`${NAMESPACE}:${sfId}`).digest("hex");
  return [
    hash.slice(0, 8),
    hash.slice(8, 12),
    "5" + hash.slice(13, 16),
    "8" + hash.slice(17, 20),
    hash.slice(20, 32),
  ].join("-");
}

/** SF Lead.Status → our canonical LeadStatus enum. */
function mapLeadStatus(raw: string | null): LeadStatus | null {
  if (!raw) return null;
  const lower = raw.toLowerCase();
  if (lower.includes("not contacted") || lower.includes("open")) return "new";
  if (lower.includes("working") || lower.includes("contacted")) return "contacted";
  if (lower.includes("qualified")) return "qualified";
  if (lower.includes("converted") || lower.includes("booked"))
    return "booked";
  if (lower.includes("unqualified") || lower.includes("lost") || lower.includes("dead"))
    return "lost";
  return null;
}

function displayName(lead: SFLead): string {
  const parts = [lead.FirstName, lead.LastName].filter(Boolean);
  return parts.length ? parts.join(" ") : lead.Email ?? "(no name)";
}

export function leadToSummary(lead: SFLead): PersonSummary {
  return {
    id: uuidFromSFId(lead.Id),
    display_name: displayName(lead),
    email: lead.Email,
    phone: lead.Phone,
    has_lead: true,
    has_consultation: false,
    last_activity_at: lead.LastModifiedDate,
    source_providers: ["salesforce"],
  };
}

export function leadToDetail(lead: SFLead): PersonDetail {
  const summary = leadToSummary(lead);
  const timeline: TimelineEvent[] = [
    {
      id: `${summary.id}-created`,
      kind: "lead_created",
      occurred_at: lead.CreatedDate,
      provider: "salesforce",
      summary: lead.LeadSource
        ? `Lead created from ${lead.LeadSource}`
        : "Lead created",
      details: {
        lead_status: lead.Status,
        lead_source: lead.LeadSource,
      },
    },
  ];
  if (lead.LastModifiedDate !== lead.CreatedDate) {
    timeline.unshift({
      id: `${summary.id}-updated`,
      kind: "lead_updated",
      occurred_at: lead.LastModifiedDate,
      provider: "salesforce",
      summary: lead.Status ? `Status: ${lead.Status}` : "Updated",
      details: { lead_status: lead.Status },
    });
  }
  return {
    summary,
    source_links: [
      {
        provider: "salesforce",
        external_id: lead.Id,
        entity: "Lead",
        confidence: 1.0,
      },
    ],
    lead: {
      status: mapLeadStatus(lead.Status),
      source: lead.LeadSource,
      created_at: lead.CreatedDate,
      updated_at: lead.LastModifiedDate,
    },
    consultations: [],
    timeline,
    carestack_origin: [],
    household_members: [],
  };
}

import type { PersonDetail, PersonSummary, TimelineEvent } from "@/lib/api/schemas";

const ALICE_UID = "11111111-1111-1111-1111-111111111111";
const BOB_UID = "22222222-2222-2222-2222-222222222222";
const CAROL_UID = "33333333-3333-3333-3333-333333333333";
// ENG-308 — Torosyan-shape fixture (3 CareStack patient_ids merged
// onto one person). Exercises the multi-link banner + expander.
const TOROSYAN_UID = "55555555-aaaa-4444-bbbb-cccccccccccc";

export const personSummaries: PersonSummary[] = [
  {
    id: ALICE_UID,
    display_name: "Alice Morgan",
    email: "alice.morgan@example.com",
    phone: "+1 (415) 555-0142",
    has_lead: true,
    has_consultation: true,
    last_activity_at: "2026-05-04T18:32:00.000Z",
    source_providers: ["salesforce", "carestack"],
  },
  {
    id: BOB_UID,
    display_name: "Bob Singh",
    email: "bob.singh@example.com",
    phone: "+1 (415) 555-0117",
    has_lead: true,
    has_consultation: false,
    last_activity_at: "2026-05-05T10:11:00.000Z",
    source_providers: ["salesforce"],
  },
  {
    id: CAROL_UID,
    display_name: "Carol Nakamura",
    email: "carol.n@example.com",
    phone: "+1 (415) 555-0193",
    has_lead: false,
    has_consultation: true,
    last_activity_at: "2026-05-05T15:50:00.000Z",
    source_providers: ["carestack"],
  },
  {
    id: TOROSYAN_UID,
    display_name: "Aram Torosyan",
    email: "aram.torosyan@example.com",
    phone: "+1 (916) 555-0188",
    has_lead: false,
    has_consultation: true,
    last_activity_at: "2026-05-04T18:32:00.000Z",
    source_providers: ["carestack"],
  },
];

const aliceTimeline: TimelineEvent[] = [
  {
    id: "aaaa1111-0000-0000-0000-000000000001",
    kind: "lead_created",
    occurred_at: "2026-04-21T14:02:00.000Z",
    provider: "salesforce",
    summary: "Lead created from Web form",
    details: { lead_status: "Open - Not Contacted", lead_source: "Web" },
  },
  {
    id: "aaaa1111-0000-0000-0000-000000000002",
    kind: "lead_updated",
    occurred_at: "2026-04-23T09:18:00.000Z",
    provider: "salesforce",
    summary: "Status moved to Working - Contacted",
    details: { lead_status: "Working - Contacted" },
  },
  {
    id: "aaaa1111-0000-0000-0000-000000000003",
    kind: "consultation_scheduled",
    occurred_at: "2026-04-29T11:30:00.000Z",
    provider: "carestack",
    summary: "Consultation booked for May 4",
    details: { scheduled_at: "2026-05-04T18:00:00Z", appointment_id: "CS-44218" },
  },
  {
    id: "aaaa1111-0000-0000-0000-000000000004",
    kind: "consultation_completed",
    occurred_at: "2026-05-04T18:32:00.000Z",
    provider: "carestack",
    summary: "Consultation completed",
    details: { appointment_id: "CS-44218" },
  },
];

const bobTimeline: TimelineEvent[] = [
  {
    id: "bbbb2222-0000-0000-0000-000000000001",
    kind: "lead_created",
    occurred_at: "2026-05-05T10:11:00.000Z",
    provider: "salesforce",
    summary: "Lead created from Phone Inquiry",
    details: { lead_status: "Open - Not Contacted", lead_source: "Phone Inquiry" },
  },
];

const carolTimeline: TimelineEvent[] = [
  {
    id: "cccc3333-0000-0000-0000-000000000001",
    kind: "consultation_scheduled",
    occurred_at: "2026-05-05T15:50:00.000Z",
    provider: "carestack",
    summary: "Consultation scheduled for next week",
    details: { scheduled_at: "2026-05-12T17:00:00Z", appointment_id: "CS-44219" },
  },
];

export const personDetails: Record<string, PersonDetail> = {
  [ALICE_UID]: {
    summary: personSummaries[0]!,
    source_links: [
      {
        provider: "salesforce",
        external_id: "00Q5j000001abcd",
        entity: "Lead",
        confidence: 1.0,
      },
      {
        provider: "carestack",
        external_id: "PT-9981",
        entity: "Patient",
        confidence: 0.92,
      },
    ],
    lead: {
      status: "qualified",
      source: "Web",
      created_at: "2026-04-21T14:02:00.000Z",
      updated_at: "2026-04-23T09:18:00.000Z",
      salesforce_status: "Working - Contacted",
      salesforce_created_at: "2026-04-21T14:02:00.000Z",
      company: "Fusion demo",
      campaign: "Spring implants",
      owner: "Taylor Owner",
      treatment_coordinator: "Jamie TC",
      is_reactivation: false,
    },
    consultations: [
      {
        id: "ccaa1111-0000-0000-0000-000000000001",
        status: "completed",
        scheduled_at: "2026-05-04T18:00:00.000Z",
        provider: "carestack",
      },
    ],
    timeline: aliceTimeline,
    // ENG-306: realistic Billed / Adjustments / Paid / Balance demo with a
    // snapshot present so the dev-mode person card exercises the populated
    // path. Numbers are illustrative, not PHI.
    financial_summary: {
      billed: 12500.0,
      adjustments: -150.0,
      paid: 8500.0,
      balance: 3850.0,
      snapshot_received_at: "2026-05-25T12:00:00.000Z",
      carestack_patient_ids: ["PT-9981"],
      patient_count: 1,
    },
    // ENG-308: single-link CareStack origin. Exercises the single-pid
    // path (no multi-link banner) AND the resolved provider+location names.
    // ENG-310: per-pid names + patient details fields populated.
    carestack_origin: [
      {
        patient_id: "PT-9981",
        earliest_activity_at: "2025-08-12T10:15:00.000Z",
        latest_activity_at: "2026-05-04T18:32:00.000Z",
        default_location_id: 10001,
        default_location_name: "Fusion Roseville",
        default_provider_id: 17,
        default_provider_name: "Dr Aram Torosyan",
        city: "Roseville",
        state: "CA",
        first_name: "Alice",
        last_name: "Morgan",
        dob: "1986-04-21",
        gender: "Female",
        marital_status: "Single",
        mobile: "+1 (415) 555-0142",
        phone_with_ext: null,
        work_phone_with_ext: null,
        email: "alice.morgan@example.com",
        address_line1: "1 Oak Lane",
        address_line2: null,
        address_zip: "95661",
        patient_identifier: "MRN-PT9981",
        account_id: "10762",
      },
    ],
    household_members: [],
  },
  [BOB_UID]: {
    summary: personSummaries[1]!,
    source_links: [
      {
        provider: "salesforce",
        external_id: "00Q5j000001efgh",
        entity: "Lead",
        confidence: 1.0,
      },
    ],
    lead: {
      status: "new",
      source: "Phone Inquiry",
      created_at: "2026-05-05T10:11:00.000Z",
      updated_at: "2026-05-05T10:11:00.000Z",
      salesforce_status: "Open - Not Contacted",
      salesforce_created_at: "2026-05-05T10:11:00.000Z",
      company: null,
      campaign: null,
      owner: "Morgan Owner",
      treatment_coordinator: null,
      is_reactivation: false,
    },
    consultations: [],
    timeline: bobTimeline,
    carestack_origin: [],
    household_members: [],
    // ENG-306: empty-state demo — Bob has no CareStack patient link so the
    // person card must render "—" everywhere instead of "$0".
    financial_summary: {
      billed: 0,
      adjustments: 0,
      paid: 0,
      balance: 0,
      snapshot_received_at: null,
      carestack_patient_ids: [],
      patient_count: 0,
    },
  },
  [CAROL_UID]: {
    summary: personSummaries[2]!,
    source_links: [
      {
        provider: "carestack",
        external_id: "PT-9985",
        entity: "Patient",
        confidence: 1.0,
      },
    ],
    lead: null,
    consultations: [
      {
        id: "ccbb2222-0000-0000-0000-000000000001",
        status: "scheduled",
        scheduled_at: "2026-05-12T17:00:00.000Z",
        provider: "carestack",
      },
    ],
    timeline: carolTimeline,
    // ENG-306: Carol has a CareStack link but no captured snapshot yet —
    // the ENG-307 backfill is the gate. The card must still render the
    // four "—" + "No balance snapshot yet" line, NOT "$0.00".
    financial_summary: {
      billed: 0,
      adjustments: 0,
      paid: 0,
      balance: 0,
      snapshot_received_at: null,
      carestack_patient_ids: ["PT-9985"],
      patient_count: 1,
    },
    // ENG-308: Carol has one CareStack link with NO captured activity
    // yet (no appointments or accounting raw_events) — exercises the
    // empty-state "—" path for earliest/latest activity.
    carestack_origin: [
      {
        patient_id: "PT-9985",
        earliest_activity_at: null,
        latest_activity_at: null,
        default_location_id: null,
        default_location_name: null,
        default_provider_id: null,
        default_provider_name: null,
        city: null,
        state: null,
        first_name: "Carol",
        last_name: "Nakamura",
        dob: null,
        gender: null,
        marital_status: null,
        mobile: null,
        phone_with_ext: null,
        work_phone_with_ext: null,
        email: null,
        address_line1: null,
        address_line2: null,
        address_zip: null,
        patient_identifier: null,
        account_id: null,
      },
    ],
    household_members: [],
  },
  // ENG-308 — Torosyan-shape: 3 CareStack patient_ids merged into one
  // person record. Drives the multi-link banner + expander UI.
  // Earliest activity comes from pid 1461274 (March 2026); the other
  // two are quieter. Half of the rows have resolved provider/location
  // names, half are null — covers BOTH the populated and empty cells in
  // the expander.
  [TOROSYAN_UID]: {
    summary: personSummaries[3]!,
    source_links: [
      {
        provider: "carestack",
        external_id: "1460847",
        entity: "Patient",
        confidence: 1.0,
        first_seen_at: "2026-04-15T11:00:00.000Z",
      },
      {
        provider: "carestack",
        external_id: "1461274",
        entity: "Patient",
        confidence: 1.0,
        first_seen_at: "2026-05-01T09:30:00.000Z",
      },
      {
        provider: "carestack",
        external_id: "2171827",
        entity: "Patient",
        confidence: 1.0,
        first_seen_at: "2026-05-15T14:20:00.000Z",
      },
    ],
    lead: null,
    consultations: [],
    timeline: [],
    financial_summary: {
      billed: 4200.0,
      adjustments: 0,
      paid: 1500.0,
      balance: 2700.0,
      snapshot_received_at: "2026-05-28T12:00:00.000Z",
      carestack_patient_ids: ["1460847", "1461274", "2171827"],
      patient_count: 3,
    },
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
        // ENG-310: per-pid name + patient details. Gaiane / Gaiane /
        // Eduard mapping in the multi-link expander.
        first_name: "Gaiane",
        last_name: "Torosyan",
        dob: "1985-04-12",
        gender: "Female",
        marital_status: "Married",
        mobile: "+1 (916) 215-4258",
        phone_with_ext: null,
        work_phone_with_ext: null,
        email: "gaiane.torosyan@example.com",
        address_line1: "100 Roseville Pkwy",
        address_line2: null,
        address_zip: "95661",
        patient_identifier: "MRN-1460847",
        account_id: "10762",
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
        first_name: "Gaiane",
        last_name: "Torosyan",
        dob: "1985-04-12",
        gender: "Female",
        marital_status: "Married",
        mobile: "+1 (916) 215-4258",
        phone_with_ext: null,
        work_phone_with_ext: null,
        email: "gaiane.torosyan@example.com",
        address_line1: "1 EDH Blvd",
        address_line2: "Suite 200",
        address_zip: "95762",
        patient_identifier: "MRN-1461274",
        account_id: "10762",
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
        dob: null,
        gender: "Male",
        marital_status: null,
        mobile: "+1 (916) 215-4258",
        phone_with_ext: null,
        work_phone_with_ext: null,
        email: null,
        address_line1: null,
        address_line2: null,
        address_zip: null,
        patient_identifier: null,
        account_id: null,
      },
    ],
    household_members: [
      {
        person_uid: "66666666-bbbb-4444-cccc-dddddddddddd",
        display_name: "Anush Torosyan",
        shared_via: "phone",
        shared_value_masked: "···4258",
      },
      {
        person_uid: "77777777-cccc-4444-dddd-eeeeeeeeeeee",
        display_name: "Karen Torosyan",
        shared_via: "both",
        shared_value_masked: "···4258",
      },
    ],
  },
};

import type {
  CsPatientMatch,
  PeopleSearchOut,
  SfPersonMatch,
} from "@/lib/api/schemas/peopleSearch";

/**
 * Synthetic identifiers used by the MSW handler for `/api/people/search`.
 *
 * The fixtures cover the five UX scenarios receptionists care about:
 *   1. Match in Salesforce only (cold lead, no chair yet)
 *   2. Match in CareStack only (existing patient, no SF lead)
 *   3. Match in both, already linked to a `identity.person`
 *   4. Match in both, NOT yet linked (the merge-candidate case)
 *   5. No match anywhere (truly new person)
 *
 * Each scenario is keyed off a known phone *or* email so the search bar
 * can be exercised end-to-end without a backend.
 */

const ALICE_UID = "11111111-1111-1111-1111-111111111111";
const DAVID_UID = "44444444-4444-4444-4444-444444444444";

// SCENARIO 1 — Salesforce-only match. New lead, never made it to CareStack.
const SF_ONLY_LEAD: SfPersonMatch = {
  id: "00Q5j000001Sf01ABC",
  object_type: "Lead",
  name: "Erin Thompson",
  phone: "+1 (415) 555-0210",
  email: "erin.t@example.com",
  status: "Open - Not Contacted",
  last_modified: "2026-05-07T11:04:00.000Z",
  linked_person_uid: null,
};

// SCENARIO 2 — CareStack-only match. Patient who came in via referral, never
// touched the SF marketing pipeline.
const CS_ONLY_PATIENT: CsPatientMatch = {
  id: 30217,
  name: "Frank Liu",
  phone: "+1 (415) 555-0322",
  email: "frank.liu@example.com",
  last_appointment: "2026-04-18T16:30:00.000Z",
  location_name: "Mission Bay",
  linked_person_uid: null,
};

// SCENARIO 3 — Both providers, already aggregated into one identity.person.
// This is "Alice Morgan" from the existing person fixtures, for cross-page
// continuity in the UI.
const ALICE_SF: SfPersonMatch = {
  id: "00Q5j000001abcd",
  object_type: "Lead",
  name: "Alice Morgan",
  phone: "+1 (415) 555-0142",
  email: "alice.morgan@example.com",
  status: "Working - Contacted",
  last_modified: "2026-04-23T09:18:00.000Z",
  linked_person_uid: ALICE_UID,
};

const ALICE_CS: CsPatientMatch = {
  id: 9981,
  name: "Alice Morgan",
  phone: "+1 (415) 555-0142",
  email: "alice.morgan@example.com",
  last_appointment: "2026-05-04T18:00:00.000Z",
  location_name: "Downtown",
  linked_person_uid: ALICE_UID,
};

// SCENARIO 4 — Both providers but NOT linked yet. This is the merge-candidate
// case the receptionist most needs to surface ("we have them in two systems —
// link them so the timeline shows both sides").
const DAVID_SF_LEAD: SfPersonMatch = {
  id: "00Q5j000001Dvd01",
  object_type: "Lead",
  name: "David Park",
  phone: "+1 (415) 555-0188",
  email: "david.park@example.com",
  status: "Open - Not Contacted",
  last_modified: "2026-05-06T14:22:00.000Z",
  linked_person_uid: null,
};

const DAVID_SF_CONTACT: SfPersonMatch = {
  id: "0035j000001Dvd02",
  object_type: "Contact",
  name: "David Park",
  phone: "+1 (415) 555-0188",
  email: "david.park@example.com",
  status: "Customer - Active",
  last_modified: "2026-05-06T14:25:00.000Z",
  linked_person_uid: null,
};

const DAVID_CS_PATIENT: CsPatientMatch = {
  id: 30255,
  name: "David Park",
  phone: "+1 (415) 555-0188",
  email: "david.park@example.com",
  last_appointment: "2026-05-01T19:15:00.000Z",
  location_name: "Mission Bay",
  linked_person_uid: null,
};

interface FixtureScenario {
  /** Identifiers that match this scenario — any one of them triggers the row. */
  phones: string[];
  emails: string[];
  sfMatches: SfPersonMatch[];
  csMatches: CsPatientMatch[];
  linkedPersonUids: string[];
}

export const PEOPLE_SEARCH_SCENARIOS: FixtureScenario[] = [
  // SCENARIO 1
  {
    phones: ["+14155550210", "4155550210", "415-555-0210"],
    emails: ["erin.t@example.com"],
    sfMatches: [SF_ONLY_LEAD],
    csMatches: [],
    linkedPersonUids: [],
  },
  // SCENARIO 2
  {
    phones: ["+14155550322", "4155550322", "415-555-0322"],
    emails: ["frank.liu@example.com"],
    sfMatches: [],
    csMatches: [CS_ONLY_PATIENT],
    linkedPersonUids: [],
  },
  // SCENARIO 3
  {
    phones: ["+14155550142", "4155550142", "415-555-0142"],
    emails: ["alice.morgan@example.com"],
    sfMatches: [ALICE_SF],
    csMatches: [ALICE_CS],
    linkedPersonUids: [ALICE_UID],
  },
  // SCENARIO 4 — David also exposes a second identity.person uid placeholder
  // to demonstrate multi-link visualisation if/when the merge ships.
  {
    phones: ["+14155550188", "4155550188", "415-555-0188"],
    emails: ["david.park@example.com"],
    sfMatches: [DAVID_SF_LEAD, DAVID_SF_CONTACT],
    csMatches: [DAVID_CS_PATIENT],
    linkedPersonUids: [],
  },
];

/**
 * Normalise a phone string: strip everything except digits and a leading
 * `+`. Mirrors what the backend's identity service will eventually do.
 */
export function normalisePhone(raw: string | undefined): string | undefined {
  if (!raw) return undefined;
  const trimmed = raw.trim();
  if (!trimmed) return undefined;
  const hasPlus = trimmed.startsWith("+");
  const digits = trimmed.replace(/\D/g, "");
  if (!digits) return undefined;
  return hasPlus ? `+${digits}` : digits;
}

export function normaliseEmail(raw: string | undefined): string | undefined {
  if (!raw) return undefined;
  const trimmed = raw.trim().toLowerCase();
  return trimmed || undefined;
}

function phoneMatches(
  scenario: FixtureScenario,
  query: string | undefined,
): boolean {
  if (!query) return false;
  const normQuery = normalisePhone(query);
  if (!normQuery) return false;
  return scenario.phones.some(
    (p) => normalisePhone(p) === normQuery,
  );
}

function emailMatches(
  scenario: FixtureScenario,
  query: string | undefined,
): boolean {
  if (!query) return false;
  const normQuery = normaliseEmail(query);
  if (!normQuery) return false;
  return scenario.emails.some((e) => e.toLowerCase() === normQuery);
}

/**
 * Run the people search against the synthetic fixtures. Returns a unified
 * `PeopleSearchOut`. SCENARIO 5 (no match) is the default when no scenario
 * keys hit.
 */
export function runPeopleSearch(input: {
  phone?: string;
  email?: string;
}): PeopleSearchOut {
  const phoneNorm = normalisePhone(input.phone);
  const emailNorm = normaliseEmail(input.email);

  const sfMatches: SfPersonMatch[] = [];
  const csMatches: CsPatientMatch[] = [];
  const linkedSet = new Set<string>();

  for (const scenario of PEOPLE_SEARCH_SCENARIOS) {
    const phoneHit = phoneMatches(scenario, input.phone);
    const emailHit = emailMatches(scenario, input.email);
    if (!phoneHit && !emailHit) continue;
    sfMatches.push(...scenario.sfMatches);
    csMatches.push(...scenario.csMatches);
    for (const uid of scenario.linkedPersonUids) linkedSet.add(uid);
  }

  return {
    query: {
      ...(phoneNorm ? { phone_normalised: phoneNorm } : {}),
      ...(emailNorm ? { email_normalised: emailNorm } : {}),
    },
    salesforce: { matches: sfMatches },
    carestack: { matches: csMatches },
    linked_person_uids: Array.from(linkedSet),
    warnings: [],
  };
}

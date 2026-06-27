/**
 * GET /api/people/search?phone=...&email=...
 *
 * Live unified people lookup across Salesforce (Lead + Contact) and
 * CareStack (Patient). Either or both of `phone` / `email` may be
 * provided; at least one is required.
 *
 * Phase 1 carve-out (per apps/web/CLAUDE.md):
 *   - Real backend logic temporarily lives in this Next.js route, not
 *     in apps/api / packages/integrations. ENG-120 will move it.
 *   - `linked_person_uids` is always `[]` here — local identity
 *     resolution requires a FastAPI hop and is deferred.
 *
 * SF: SOQL via @/lib/sf/client (read-only). Phone matching uses LIKE
 * on the raw digits and the last 7, since SF stores phones in
 * operator-entered formats (parens, dashes, +1, etc.).
 *
 * CS: POST /api/v2.0/patients/search with a `searchTerm` (full-text)
 * — the spec's `filterByFields` schema for type is undocumented in
 * the local copy, and CareStack accepts the same identifier as a
 * search term across phone/email/identifier fields.
 */
import { NextResponse, type NextRequest } from "next/server";
import {
  soql,
  sosl,
  SFNotConnectedError,
  type SoslSearchRecord,
} from "@/lib/sf/client";
import { csPost, CSNotConnectedError } from "@/lib/cs/client";

export const dynamic = "force-dynamic";

interface SfRow {
  Id: string;
  FirstName?: string | null;
  LastName?: string | null;
  Email?: string | null;
  Phone?: string | null;
  Status?: string | null;
  LastModifiedDate: string;
}

interface CsPatient {
  patientId: number;
  firstName?: string | null;
  lastName?: string | null;
  mobile?: string | null;
  email?: string | null;
  locationName?: string | null;
}

interface SfMatch {
  id: string;
  object_type: "Lead" | "Contact";
  name: string | null;
  phone: string | null;
  email: string | null;
  status: string | null;
  last_modified: string;
  linked_person_uid: string | null;
}

interface CsMatch {
  id: number;
  name: string | null;
  phone: string | null;
  email: string | null;
  last_appointment: string | null;
  location_name: string | null;
  linked_person_uid: string | null;
}

interface ProviderWarning {
  provider: "salesforce" | "carestack";
  code: "not_connected" | "search_failed";
  message: string;
}

function digitsOnly(s: string): string {
  return s.replace(/\D/g, "");
}

function escSoql(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

function fullName(first?: string | null, last?: string | null): string | null {
  const parts = [first, last].filter((p): p is string => Boolean(p));
  return parts.length > 0 ? parts.join(" ") : null;
}

/**
 * SF REST API returns datetimes like `2026-01-15T12:34:56.000+0000`
 * (RFC 822 timezone, no colon). Zod's `z.string().datetime()` is strict
 * ISO-8601 — it wants `Z` or `+00:00`. Round-trip through Date to get
 * the canonical `...Z` form. Returns the input unchanged on parse error
 * (lets Zod surface a clearer error than a NaN time).
 */
function isoDateTime(s: string): string {
  const ts = Date.parse(s);
  return Number.isFinite(ts) ? new Date(ts).toISOString() : s;
}

/**
 * Escape a literal for use inside a SOSL `FIND {...}` clause.
 * Per Salesforce docs the reserved chars are
 * `? & | ! { } [ ] ( ) ^ ~ * : \ " ' + -`
 * — back-slash any of them. Plus we escape backslash itself first.
 */
function escSosl(s: string): string {
  return s.replace(/[\\?&|!{}\[\]()^~*:"'+\-]/g, (c) => `\\${c}`);
}

function mapSfRow(
  row: SfRow,
  object_type: "Lead" | "Contact",
): SfMatch {
  return {
    id: row.Id,
    object_type,
    name: fullName(row.FirstName, row.LastName),
    phone: row.Phone ?? null,
    email: row.Email ?? null,
    status: row.Status ?? null,
    last_modified: isoDateTime(row.LastModifiedDate),
    linked_person_uid: null,
  };
}

/**
 * Generate the common operator-entered phone formats for a given
 * digit-only input. We use these as LIKE patterns when SOSL misses
 * (e.g. the SOSL search index hasn't caught up after a recent edit
 * or the phone lives in a non-standard field).
 *
 * For US 10-digit (`9166642270`) we emit `(916) 664-2270`,
 * `916-664-2270`, `916.664.2270`, `916 664 2270`, `+19166642270`,
 * `+1 916 664 2270`, plus the bare digits and the last-7 fallback.
 * For 11-digit `1XXXXXXXXXX` we additionally include `+1...`.
 */
function phoneLikePatterns(digits: string): string[] {
  const out = new Set<string>();
  if (digits.length < 7) return [];
  out.add(digits);
  out.add(digits.slice(-7));
  out.add(digits.slice(-10));

  const us =
    digits.length === 11 && digits.startsWith("1") ? digits.slice(1) :
    digits.length === 10 ? digits :
    null;

  if (us) {
    const a = us.slice(0, 3);
    const b = us.slice(3, 6);
    const c = us.slice(6);
    out.add(`(${a}) ${b}-${c}`);
    out.add(`${a}-${b}-${c}`);
    out.add(`${a}.${b}.${c}`);
    out.add(`${a} ${b} ${c}`);
    out.add(`+1${us}`);
    out.add(`+1 ${a} ${b} ${c}`);
    out.add(`+1-${a}-${b}-${c}`);
    out.add(`1-${a}-${b}-${c}`);
  }

  if (digits.length >= 7) {
    const last7 = digits.slice(-7);
    out.add(`${last7.slice(0, 3)}-${last7.slice(3)}`);
  }

  return Array.from(out);
}

const SF_PHONE_FIELDS_BY_OBJECT: Record<"Lead" | "Contact", string[]> = {
  Lead: ["Phone", "MobilePhone"],
  Contact: ["Phone", "MobilePhone", "HomePhone", "OtherPhone"],
};

async function searchSf(phone?: string, email?: string): Promise<SfMatch[]> {
  const out = new Map<string, SfMatch>();
  const fields =
    "Id, FirstName, LastName, Email, Phone, Status, LastModifiedDate";

  // PHONE — SOSL `IN PHONE FIELDS` first. Fast and format-agnostic when
  // the SOSL search index has caught up.
  let sosLHit = false;
  if (phone) {
    const digits = digitsOnly(phone);
    if (digits.length >= 7) {
      const term = escSosl(digits);
      const query =
        `FIND {${term}} IN PHONE FIELDS RETURNING ` +
        `Lead(${fields} WHERE IsDeleted = false LIMIT 25), ` +
        `Contact(${fields} WHERE IsDeleted = false LIMIT 25)`;
      try {
        const result = await sosl(query);
        for (const rec of result.searchRecords) {
          const t = rec.attributes.type;
          if (t !== "Lead" && t !== "Contact") continue;
          const row = rec as unknown as SfRow;
          const match = mapSfRow(row, t);
          if (!out.has(match.id)) {
            out.set(match.id, match);
            sosLHit = true;
          }
        }
      } catch (e) {
        if (e instanceof SFNotConnectedError) throw e;
        console.error("SF SOSL phone search failed:", e);
      }
    }

    // SOQL fallback — SOSL's index can lag for fresh records or miss
    // non-standard phone fields. Run multi-format LIKE on Phone +
    // MobilePhone (and HomePhone/OtherPhone for Contact).
    if (!sosLHit && digits.length >= 7) {
      const patterns = phoneLikePatterns(digits);
      const queries: Array<{
        object_type: "Lead" | "Contact";
        query: string;
      }> = (["Lead", "Contact"] as const).map((obj) => {
        const conds = SF_PHONE_FIELDS_BY_OBJECT[obj].flatMap((f) =>
          patterns.map((p) => `${f} LIKE '%${escSoql(p)}%'`),
        );
        return {
          object_type: obj,
          query:
            `SELECT ${fields} FROM ${obj} ` +
            `WHERE (${conds.join(" OR ")}) AND IsDeleted = false LIMIT 25`,
        };
      });

      const results = await Promise.all(
        queries.map(async ({ object_type, query }): Promise<SfMatch[]> => {
          try {
            const r = await soql<SfRow>(query);
            return r.records.map((row) => mapSfRow(row, object_type));
          } catch (e) {
            if (e instanceof SFNotConnectedError) throw e;
            console.error(`SF ${object_type} SOQL fallback failed:`, e);
            return [];
          }
        }),
      );
      for (const m of results.flat()) {
        if (!out.has(m.id)) out.set(m.id, m);
      }
    }
  }

  // EMAIL — SOQL exact-match on canonical lower-cased value.
  if (email) {
    const safe = escSoql(email.trim().toLowerCase());
    const where = `Email = '${safe}'`;
    const queries: Array<{ object_type: "Lead" | "Contact"; query: string }> = [
      {
        object_type: "Lead",
        query: `SELECT ${fields} FROM Lead WHERE ${where} AND IsDeleted = false LIMIT 25`,
      },
      {
        object_type: "Contact",
        query: `SELECT ${fields} FROM Contact WHERE ${where} AND IsDeleted = false LIMIT 25`,
      },
    ];
    const results = await Promise.all(
      queries.map(async ({ object_type, query }): Promise<SfMatch[]> => {
        try {
          const r = await soql<SfRow>(query);
          return r.records.map((row) => mapSfRow(row, object_type));
        } catch (e) {
          if (e instanceof SFNotConnectedError) throw e;
          console.error(`SF ${object_type} email search failed:`, e);
          return [];
        }
      }),
    );
    for (const m of results.flat()) {
      if (!out.has(m.id)) out.set(m.id, m);
    }
  }

  return Array.from(out.values());
}

/**
 * Most-recent appointment date for a CareStack patient.
 *
 * Uses POST /scheduler/api/v1.0/appointments/search with
 * `filterQuery.PatientId = [id]`, ordered desc by dateTimeUTC,
 * pageSize=1 — we only need the latest one.
 *
 * Important: the local CareStack spec at
 * `docs/integrations/carestack/search/appointments.md` describes the
 * envelope as `{ Result: [...], TotalCount }`, but the live API
 * actually returns `{ result: [...], totalRecords }` (camelCase).
 * Both are accepted defensively. Likewise `dateTime` arrives without
 * a timezone suffix — we treat it as UTC (CareStack's stored value).
 *
 * Returns ISO datetime string, or null if the patient has no
 * appointments / the call fails.
 */
async function fetchLastAppointment(patientId: number): Promise<string | null> {
  interface ApptItem {
    dateTime?: string;
    dateTimeUTC?: string;
  }
  interface ApptResp {
    result?: ApptItem[];
    Result?: ApptItem[];
    totalRecords?: number;
    TotalCount?: number;
  }
  try {
    const resp = await csPost<ApptResp>(
      "scheduler/api/v1.0/appointments/search",
      {
        filterQuery: { PatientId: [patientId] },
        orderBy: "dateTimeUTC desc",
        pageIndex: 1,
        pageSize: 1,
      },
    );
    const list = resp.result ?? resp.Result ?? [];
    const first = list[0];
    // Prefer .dateTime (clinic-local naive ISO) over .dateTimeUTC.
    // Empirically: CareStack returns `2026-05-11T12:10:00` for an
    // appointment at noon clinic-local; treating it as UTC yields a
    // misleading 5 AM in the operator's PT browser. We hand the raw
    // string back and let the UI render in whatever TZ the operator
    // sees the rest of the dashboard in.
    const dt = first?.dateTime ?? first?.dateTimeUTC;
    if (!dt) return null;
    return isoDateTime(dt);
  } catch (e) {
    console.error(
      `CS appointments fetch failed for patient ${patientId}:`,
      e,
    );
    return null;
  }
}

async function searchCs(phone?: string, email?: string): Promise<CsMatch[]> {
  const matches = new Map<number, CsMatch>();
  const terms: string[] = [];

  if (phone) {
    const digits = digitsOnly(phone);
    if (digits.length >= 7) {
      terms.push(digits);
      if (digits.length === 10) terms.push(`+1${digits}`);
    }
  }
  if (email) terms.push(email.trim().toLowerCase());
  if (terms.length === 0) return [];

  for (const term of terms) {
    try {
      const result = await csPost<
        CsPatient[] | { data?: CsPatient[]; patients?: CsPatient[] }
      >("api/v2.0/patients/search", { searchTerm: term, limit: 25 });
      const list = Array.isArray(result)
        ? result
        : (result.patients ?? result.data ?? []);
      for (const p of list) {
        if (matches.has(p.patientId)) continue;
        matches.set(p.patientId, {
          id: p.patientId,
          name: fullName(p.firstName, p.lastName),
          phone: p.mobile ?? null,
          email: p.email ?? null,
          last_appointment: null,
          location_name: p.locationName ?? null,
          linked_person_uid: null,
        });
      }
    } catch (e) {
      if (e instanceof CSNotConnectedError) {
        throw e;
      }
      console.error(`CS search failed for term "${term}":`, e);
    }
  }

  // Fan out one appointment lookup per match. Capped: if we got >5
  // patients (rare in real ops), skip — keeps total latency bounded.
  const matchList = Array.from(matches.values());
  if (matchList.length > 0 && matchList.length <= 5) {
    const lastAppts = await Promise.all(
      matchList.map((m) => fetchLastAppointment(m.id)),
    );
    matchList.forEach((m, i) => {
      m.last_appointment = lastAppts[i] ?? null;
    });
  }

  return matchList;
}

export async function GET(req: NextRequest) {
  const phone = req.nextUrl.searchParams.get("phone") ?? undefined;
  const email = req.nextUrl.searchParams.get("email") ?? undefined;

  if (!phone && !email) {
    return NextResponse.json(
      {
        error: {
          code: "VALIDATION",
          message: "At least one of `phone` or `email` is required",
          details: {},
        },
      },
      { status: 400 },
    );
  }

  const phoneNorm = phone ? digitsOnly(phone) : undefined;
  const emailNorm = email ? email.trim().toLowerCase() : undefined;

  const [sfResult, csResult] = await Promise.allSettled([
    searchSf(phone, email),
    searchCs(phone, email),
  ]);

  const warnings: ProviderWarning[] = [];

  if (
    sfResult.status === "rejected" &&
    sfResult.reason instanceof SFNotConnectedError
  ) {
    warnings.push({
      provider: "salesforce",
      code: "not_connected",
      message: sfResult.reason.message,
    });
  } else if (sfResult.status === "rejected") {
    console.error("SF people search failed:", sfResult.reason);
    warnings.push({
      provider: "salesforce",
      code: "search_failed",
      message: "Salesforce search failed.",
    });
  }

  if (
    csResult.status === "rejected" &&
    csResult.reason instanceof CSNotConnectedError
  ) {
    warnings.push({
      provider: "carestack",
      code: "not_connected",
      message: csResult.reason.message,
    });
  } else if (csResult.status === "rejected") {
    console.error("CareStack people search failed:", csResult.reason);
    warnings.push({
      provider: "carestack",
      code: "search_failed",
      message: "CareStack search failed.",
    });
  }

  const sfMatches: SfMatch[] =
    sfResult.status === "fulfilled" ? sfResult.value : [];
  const csMatches: CsMatch[] =
    csResult.status === "fulfilled" ? csResult.value : [];

  return NextResponse.json({
    query: {
      phone_normalised: phoneNorm,
      email_normalised: emailNorm,
    },
    salesforce: { matches: sfMatches },
    carestack: { matches: csMatches },
    linked_person_uids: [],
    warnings,
  });
}

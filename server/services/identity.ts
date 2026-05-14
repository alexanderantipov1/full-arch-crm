import { storage } from "../storage";
import type { Person } from "@shared/schema";

// ── IdentityService ───────────────────────────────────────────────────────
// The single place that resolves "is this a new human, or one we already
// know about?". Per fusion_crm doctrine, every domain (PHI, ops, audit,
// integrations, …) references a global `person_uid` UUID. This service
// produces and reconciles that UUID.
//
// Identity is pre-PHI: knowing two records belong to the same human does
// not by itself disclose clinical data, so IdentityService does NOT go
// through PhiService. The downstream `PhiService.getPatient` etc. still
// gate access to the actual clinical rows.
//
// Matching strategy (in order, first hit wins):
//   1. email (normalized: trim + lowercase)
//   2. phone (normalized: digits only)
//   3. (firstName, lastName, dateOfBirth) exact match
// If none match, a new `persons` row is created.

const NON_DIGIT = /\D+/g;

export function normalizeEmail(email: string | null | undefined): string | null {
  if (!email) return null;
  const trimmed = email.trim().toLowerCase();
  return trimmed.length > 0 ? trimmed : null;
}

export function normalizePhone(phone: string | null | undefined): string | null {
  if (!phone) return null;
  const digits = phone.replace(NON_DIGIT, "");
  return digits.length > 0 ? digits : null;
}

export type IdentitySource =
  | "patient"
  | "lead"
  | "intake"
  | "manual"
  | "carestack"
  | "salesforce"
  | "backfill";

export interface ExternalIdHint {
  system: string;          // "salesforce" | "carestack" | "stripe" | ...
  id: string;              // the external system's identifier
  kind?: string | null;    // optional sub-type (e.g. SF "Lead" vs "Contact")
}

export interface ResolveOrCreatePersonInput {
  firstName?: string | null;
  lastName?: string | null;
  email?: string | null;
  phone?: string | null;
  dateOfBirth?: string | null;
  source: IdentitySource;
  // Optional external-system identifiers. Checked BEFORE email/phone — an
  // external system that has its own dedup is more authoritative than
  // contact-info heuristics. Any external IDs that don't already match a
  // person are linked to whatever person is ultimately resolved/created.
  externalIds?: ExternalIdHint[];
}

export interface ResolveResult {
  person: Person;
  // What matched, or `created` if no match was found.
  via: "external_id" | "email" | "phone" | "name_dob" | "created";
}

// Follow `merged_into_id` until we land on a "live" person. Cycles are
// guarded by a depth cap — three hops is more than enough for any
// realistic merge chain, and lets us detect a bad data state instead of
// hanging.
async function resolveMergedInto(person: Person): Promise<Person> {
  let current = person;
  for (let i = 0; i < 3 && current.mergedIntoId; i++) {
    const next = await storage.getPerson(current.mergedIntoId);
    if (!next) break;
    current = next;
  }
  return current;
}

// Link any unmatched external IDs to the final person. Silently skips
// links that would violate the (system, id) uniqueness constraint, which
// can happen in a race (two writers resolving the same external ID
// concurrently) — neither caller is wrong, and the row is already linked.
async function linkUnmatchedExternalIds(
  personUid: string,
  externalIds: ExternalIdHint[] | undefined,
  alreadyMatchedSystem: string | null,
  alreadyMatchedId: string | null,
): Promise<void> {
  if (!externalIds || externalIds.length === 0) return;
  for (const ext of externalIds) {
    if (ext.system === alreadyMatchedSystem && ext.id === alreadyMatchedId) continue;
    try {
      await storage.linkPersonExternalId({
        personUid,
        externalSystem: ext.system,
        externalId: ext.id,
        externalKind: ext.kind ?? null,
        lastSyncedAt: null,
        metadata: null,
      } as any);
    } catch (err: any) {
      // Unique-constraint violation = already linked to some person.
      // Don't fail the resolution.
      if (!String(err?.message ?? "").includes("uniq_person_external_ids_system_id")) {
        throw err;
      }
    }
  }
}

export async function resolveOrCreatePerson(input: ResolveOrCreatePersonInput): Promise<ResolveResult> {
  const email = normalizeEmail(input.email);
  const phone = normalizePhone(input.phone);

  // 0. External-ID match — highest trust. Walk every hint until one
  //    resolves. If multiple hints match DIFFERENT persons, the first one
  //    wins; the caller should run a merge after if that's a real conflict.
  if (input.externalIds && input.externalIds.length > 0) {
    for (const ext of input.externalIds) {
      const match = await storage.findPersonByExternalId(ext.system, ext.id);
      if (match) {
        const resolved = await resolveMergedInto(match);
        await linkUnmatchedExternalIds(resolved.id, input.externalIds, ext.system, ext.id);
        return { person: resolved, via: "external_id" };
      }
    }
  }

  // 1. Email match.
  if (email) {
    const match = await storage.findPersonByEmail(email);
    if (match) {
      const resolved = await resolveMergedInto(match);
      await linkUnmatchedExternalIds(resolved.id, input.externalIds, null, null);
      return { person: resolved, via: "email" };
    }
  }

  // 2. Phone match.
  if (phone) {
    const match = await storage.findPersonByPhone(phone);
    if (match) {
      const resolved = await resolveMergedInto(match);
      await linkUnmatchedExternalIds(resolved.id, input.externalIds, null, null);
      return { person: resolved, via: "phone" };
    }
  }

  // 3. (firstName, lastName, dateOfBirth) match — guards against the
  //    common case where two intake forms have slightly different contact
  //    info but identify the same human.
  if (input.firstName && input.lastName && input.dateOfBirth) {
    const match = await storage.findPersonByNameDob(input.firstName, input.lastName, input.dateOfBirth);
    if (match) {
      const resolved = await resolveMergedInto(match);
      await linkUnmatchedExternalIds(resolved.id, input.externalIds, null, null);
      return { person: resolved, via: "name_dob" };
    }
  }

  // 4. No match — create a new person and link any provided external IDs.
  const created = await storage.createPerson({
    firstName: input.firstName ?? null,
    lastName: input.lastName ?? null,
    dateOfBirth: input.dateOfBirth ?? null,
    email,
    phone,
    firstSeenSource: input.source,
    mergedIntoId: null,
  } as any);
  await linkUnmatchedExternalIds(created.id, input.externalIds, null, null);

  return { person: created, via: "created" };
}

// Manually link an external ID to an existing person. Useful when a sync
// worker discovers a new external record that doesn't show up in normal
// resolution (e.g. a Salesforce contact created directly in SF that needs
// to map to a CRM patient that already exists here).
export async function linkExternalId(
  personUid: string,
  hint: ExternalIdHint,
  metadata?: Record<string, unknown>,
): Promise<void> {
  await storage.linkPersonExternalId({
    personUid,
    externalSystem: hint.system,
    externalId: hint.id,
    externalKind: hint.kind ?? null,
    lastSyncedAt: null,
    metadata: metadata ?? null,
  } as any);
}

export async function findPersonByExternalId(
  system: string,
  externalId: string,
): Promise<Person | undefined> {
  const match = await storage.findPersonByExternalId(system, externalId);
  return match ? await resolveMergedInto(match) : undefined;
}

export async function getPerson(id: string): Promise<Person | undefined> {
  const person = await storage.getPerson(id);
  if (!person) return undefined;
  return resolveMergedInto(person);
}

// Merge two persons. The "winner" keeps its UUID; the "loser" gets
// `merged_into_id = winner.id`. Downstream rows that point at the loser's
// UUID are NOT rewritten — `resolveMergedInto` follows the link instead.
// Manual operation; not called in any automatic flow today.
export async function mergePersons(loserId: string, winnerId: string): Promise<void> {
  if (loserId === winnerId) {
    throw new Error("Cannot merge a person into themselves");
  }
  const loser = await storage.getPerson(loserId);
  const winner = await storage.getPerson(winnerId);
  if (!loser) throw new Error(`Loser person ${loserId} not found`);
  if (!winner) throw new Error(`Winner person ${winnerId} not found`);
  await storage.setPersonMergedInto(loserId, winnerId);
}

export const identityService = {
  resolveOrCreatePerson,
  getPerson,
  mergePersons,
  linkExternalId,
  findPersonByExternalId,
  normalizeEmail,
  normalizePhone,
};

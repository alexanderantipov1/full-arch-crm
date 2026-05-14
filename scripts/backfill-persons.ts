// Backfill script — populates `persons` + `patients.personUid` / `leads.personUid`
// for legacy rows that existed before identity unification landed.
//
// Run order:
//   1. Apply schema (npm run db:push) so `persons` exists and the
//      `personUid` columns are present on patients + leads.
//   2. Run this script ONCE per environment:
//        tsx scripts/backfill-persons.ts
//      Idempotent — re-running skips rows that already have personUid.
//
// Strategy:
//   - Patients first (highest-trust identity source).
//   - For each patient: call resolveOrCreatePerson; write the returned
//     UUID back via storage.setPatientPersonUid.
//   - Then leads. Leads with the same email/phone/name+DOB as an
//     already-backfilled patient will resolve to the same person_uid.
//   - A summary is printed at the end (patients linked, leads linked,
//     new persons created, deduped leads).
//
// Safety:
//   - Read-only against patient/lead PHI columns; only writes are to the
//     new `personUid` columns and to the `persons` table itself.
//   - If a patient already has personUid set, it's left alone — supports
//     partial backfills (e.g. if the script is interrupted and restarted).

import { db } from "../server/db";
import { patients, leads } from "@shared/schema";
import { storage } from "../server/storage";
import { resolveOrCreatePerson } from "../server/services/identity";
import { isNull } from "drizzle-orm";

interface Summary {
  patientsScanned: number;
  patientsLinked: number;
  leadsScanned: number;
  leadsLinked: number;
  personsCreated: number;
  personsReused: number;
}

async function backfillPatients(summary: Summary): Promise<void> {
  // Only the rows that don't yet have a person_uid.
  const rows = await db.select().from(patients).where(isNull(patients.personUid));
  summary.patientsScanned = rows.length;

  for (const p of rows) {
    const { person, via } = await resolveOrCreatePerson({
      firstName: p.firstName,
      lastName: p.lastName,
      email: p.email,
      phone: p.phone,
      dateOfBirth: p.dateOfBirth,
      source: "backfill",
    });
    if (via === "created") summary.personsCreated++;
    else summary.personsReused++;

    await storage.setPatientPersonUid(p.id, person.id);
    summary.patientsLinked++;
  }
}

async function backfillLeads(summary: Summary): Promise<void> {
  const rows = await db.select().from(leads).where(isNull(leads.personUid));
  summary.leadsScanned = rows.length;

  for (const l of rows) {
    const { person, via } = await resolveOrCreatePerson({
      firstName: l.firstName,
      lastName: l.lastName,
      email: l.email,
      phone: l.phone,
      // Leads don't have DOB on this schema — pass null so the matcher
      // falls back to email or phone only.
      dateOfBirth: null,
      source: "backfill",
    });
    if (via === "created") summary.personsCreated++;
    else summary.personsReused++;

    await storage.setLeadPersonUid(l.id, person.id);
    summary.leadsLinked++;
  }
}

async function main(): Promise<void> {
  const summary: Summary = {
    patientsScanned: 0,
    patientsLinked: 0,
    leadsScanned: 0,
    leadsLinked: 0,
    personsCreated: 0,
    personsReused: 0,
  };

  console.log("[backfill] starting…");
  await backfillPatients(summary);
  console.log(
    `[backfill] patients: scanned ${summary.patientsScanned}, linked ${summary.patientsLinked}`,
  );

  await backfillLeads(summary);
  console.log(
    `[backfill] leads:    scanned ${summary.leadsScanned}, linked ${summary.leadsLinked}`,
  );

  console.log(
    `[backfill] persons:  created ${summary.personsCreated}, matched-and-reused ${summary.personsReused}`,
  );
  console.log("[backfill] done.");
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("[backfill] FAILED:", err);
    process.exit(1);
  });

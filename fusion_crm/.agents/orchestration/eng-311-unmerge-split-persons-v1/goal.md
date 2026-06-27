# Goal — ENG-311: un-merge 3,416 wrong-merged CareStack persons

ENG-309 stopped NEW household-merges (DOB/SSN hard-block). This ticket
cleans up the 3,416 EXISTING wrong-merged persons the old resolver
produced — whole households (parents + children) collapsed into one
`person.id`, so financial aggregates sum across distinct humans.

Ship a background un-merge script that splits each wrong-merged person
into N persons — one per `(dob, ssn)` bucket. Largest bucket stays on
the original person.id; each other bucket spawns a new person. Source
links repartition with their bucket; downstream financials re-attribute
automatically (they key on CareStack patient_id, not person_uid). One
`audit.access_log` row per split.

Linear: ENG-311 (High)
URL: https://linear.app/fusion-dental-implants/issue/ENG-311/un-merge-backfill-split-3416-wrong-merged-carestack-persons-post-eng
Parent: ENG-309 — Related: ENG-309 (the resolver fix this complements).

## Audit baseline (this session, prod tenant)

- 50,084 persons with CS link / 4,775 multi-link / **3,416 wrong-merged
  (DOB OR SSN mismatch)**.
- Largest collisions: 5 distinct humans in one person (Perevertov,
  Tabaie, Allen, etc).

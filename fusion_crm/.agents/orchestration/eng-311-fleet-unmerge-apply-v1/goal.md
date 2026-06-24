# Goal — ENG-311 Fleet Un-Merge `--apply`

Execute the operator-gated fleet split of wrong-merged CareStack persons that ENG-311's
DO-NOT-MERGE #3 deferred. Run the already-merged
`infra/scripts/split_wrong_merged_persons.py` with `--apply` against the local Docker
Postgres (`:5434`, prod-copy dataset), tenant `11111111-1111-4111-8111-111111111111`.

Each wrong-merged `identity.person` is split into one Person per `(dob, ssn)` bucket so
financial aggregates (Paid / Balance / Billed / Adjustments) stop summing across distinct
humans collapsed by the pre-ENG-309 resolver.

Scale (live audit 2026-06-02): **3,808** wrong-merged persons (DOB OR SSN mismatch).

Done when: audit count → 0 / near-0, audit.access_log carries one split row per split,
a live person card attributes finances per-human, and the run is reversible from a
pre-apply dump.

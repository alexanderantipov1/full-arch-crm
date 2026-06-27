# Acceptance — Layer A (ENG-341)

- A second person can hold a phone/email value already held by another person
  (no IntegrityError; both `person_identifier` rows persist).
- A 1:1 key (ssn, carestack_patient_id, carestack accountId, salesforce ids,
  portal) still rejects a duplicate `(kind, value)` across persons.
- Migration is idempotent and reversible (upgrade + downgrade); it pre-checks
  for existing duplicate values among the unique kinds and fails loudly if any
  exist (no silent index-creation failure).
- `create_person` / `attach_identifier` persist shared phone/email on a 2nd
  person; same-person re-attach stays idempotent ("exists"); unique-kind
  collision still guarded.
- No PHI in logs. No infra/env/deploy changes in A. Existing identity tests
  green + new tests for the above.

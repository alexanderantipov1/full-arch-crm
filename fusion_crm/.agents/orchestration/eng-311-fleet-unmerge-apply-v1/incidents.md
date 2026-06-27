# Incidents — ENG-311 Fleet Un-Merge `--apply`

- 2026-06-02T00:50Z | Count drift (not a bug) | Live `audit_identity_merges.py` reports
  **3,808** wrong_merged_persons, vs ENG-311 ticket's victim set of **3,416** and the
  kickoff's "~3,415 remaining". Delta ≈ +390. Likely cause: additional CareStack patient
  data pulled into `:5434` after the ticket audit (scanned_multi_pid_persons now 4,778).
  Not a blocker — the split predicate is idempotent and operates on current `(dob,ssn)`
  buckets. Number of record for this run = 3,808.

- 2026-06-02T01:05Z | Adversarial review (Workflow wf_e10505fb-c34) verdict + triage |
  aggregated_pass=FALSE. Lenses: no-PHI-leak=PASS, idempotency-safety=PASS,
  correctness=FAIL(major). The single major (is_real_code_bug=true): "surviving
  person.dob/ssn never UPDATEd post-split -> stale demographic signal -> ENG-309 veto
  could falsely reject re-ingest of the surviving human's own pids."
  TRIAGE = ACCEPT (spec-vs-reality / empirically inert). VERIFIED against live code + data:
    * service.py:240-244 veto DOES read person.dob/ssn (reviewer right about the mechanism).
    * BUT identity.person.dob is populated in 0/110042 rows, ssn in 1/110042 (global query).
      Example 01004b57: dob=NULL, ssn=NULL. CareStack persons were bulk-created without
      dob/ssn (the reason ENG-312 backfill exists, still open).
    * With person.dob=NULL the veto's "candidate.dob is not None" guard means it never
      fires on the surviving person -> the false-reject downstream cannot occur.
    * Post-split: surviving stays NULL (consistent with the other ~106K persons; ENG-312
      backfills uniformly later); NEW persons get correct bucket dob/ssn (strict improvement).
  Minor (non-blocking): commit-every flushes on `split` not `processed` (WAL pressure only
  under high error rate; expected error_count~0). Lexicographic tie-break picks numerically
  larger pid (matches spec; financial attribution keys on patient_id, not person_uid, so
  survivor choice does not affect $$ correctness).
  OPTIONAL FOLLOW-UP (not a blocker): either have the split also SET surviving person.dob/ssn
  from its bucket, OR (preferred, more uniform) defer to ENG-312 to backfill dob/ssn for ALL
  persons after the split. Sequencing is clean: split first, ENG-312 second.

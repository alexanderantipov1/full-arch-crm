# Goal — ENG-312 person.dob/ssn backfill

Ship `infra/scripts/backfill_person_dob_ssn.py` that populates `identity.person.dob`
and `identity.person.ssn` (currently NULL in 0/110042 and 1/110042 rows) from the latest
`carestack.patient.upsert` payload per linked patient_id, write-once (set-where-NULL).

This activates the ENG-309 DOB/SSN hard veto on the existing population — the veto only
fires when the candidate Person row has a value, and today it has none.

Done when the script + tests are merged green and a dry-run on local `:5434` shows a
sane plan. The real `--apply` is a separate operator-gated run (like ENG-311).

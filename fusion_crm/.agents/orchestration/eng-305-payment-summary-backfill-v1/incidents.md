# Incidents — ENG-305

## 2026-05-31 — Adversarial review findings (accepted as residual risks)

Workflow `w5s0j5laj` (3 Sonnet lenses: correctness / mocking / live-signal) ran
against worker commit `50da948` on branch `eng-305-eng-305`. Two findings were
surfaced; both were judged non-blocking and accepted as residual risks before
verifier handoff.

### Finding 1 — Double-flush on commit boundary (correctness, "major")

**File:** `packages/ingest/carestack_payment_summary_service.py:416-422`
**Verdict:** ACCEPT — deliberate design choice, documented in docstring.

When `len(patient_ids) % commit_every == 0`, the mid-loop flush
(line 418-419) and the final flush (line 421-422) both fire. The worker's
own docstring acknowledges this: *"The final flush at end is unconditional
when any work was done — better one redundant commit than a lost batch."*

The second commit is a no-op (nothing new since the prior flush) and carries
zero functional risk. Net cost: one extra `await commit()` call per sweep
whose patient count is an exact multiple of `commit_every`.

If a follow-up wants to eliminate the duplication, the minimal fix is:

```python
if did_any_work and commit is not None and processed % commit_every != 0:
    await commit()
```

Not pursued in this ticket — the reviewer's "major" severity is overstated
given the documented safety rationale.

### Finding 2 — Test name vs coverage mismatch (live-signal, "minor")

**File:** `tests/ingest/test_carestack_accounting_transaction_service.py:1278-1309`
**Verdict:** ACCEPT — cosmetic; the unlinked path IS covered elsewhere.

The test `test_import_patient_ids_excludes_skipped_unlinked_and_non_payment_rows`
exercises only two of the three exclusion paths it names (no-patientId and
non-payment). The unlinked-patient branch (`find_source_link → None`) is
covered by `test_row_with_unlinked_patient_is_captured_but_skipped` at
line ~500, but that earlier test does not additionally assert
`result.patient_ids == []`.

Follow-up improvement (optional): either rename the combined test to
`..._excludes_no_patientid_and_non_payment_rows`, or extend the existing
unlinked test to also assert the empty `patient_ids`.

### Pass — Mocking lens (no findings)

All five mocking claims passed cleanly. Zero real-network risk: every new
test wires `AsyncMock` / `MagicMock` for the CareStack client; `--dry-run`
backfill test asserts `client_factory.assert_not_called()`; sleep is
injected via `_SleepRecorder` (never real `asyncio.sleep`); no `requests`,
`httpx`, or `carestack.com` URLs anywhere in the test diff.

You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: **ENG-305**
(https://linear.app/fusion-dental-implants/issue/ENG-305/throttled-payment-summary-backfill-authoritative-patient-balance).
Isolated git worktree. Implement → verify → write a report. Do NOT touch `main`,
do NOT push, do NOT open a PR. Commit to YOUR worktree branch only once green;
the Orchestrator integrates.

## Mission (data-only)

Bring per-patient **authoritative balance** to Fusion CRM by pulling CareStack
`payment-summary` (`balanceDuePatient` + `balanceDueInsurance`,
`appliedPatientPayment` + `appliedInsPayments`) for every linked patient that
has payments. Today we have it for **50** patients; we need it for **1803**.
This ticket adds the data path. UI for Billed/Adjustments/Paid/Balance on the
person card is a SEPARATE follow-up ticket — do NOT build UI in this one.

## Why payment-summary (do not re-derive)

The authoritative balance CANNOT be derived from the accounting journal
(full double-entry; per-folio debit−credit nets to 0 — verified on
patient 1751021). The trustworthy source is `payment-summary`, which we
already consume for dashboard Outstanding / AR-risk.

## Pre-flight facts (already audited — do NOT re-investigate)

### Backoff already exists in `_fetch_summary_with_backoff`

- `packages/ingest/carestack_payment_summary_service.py:50-52` — retryable status
  codes: `frozenset({429, 500, 502, 503, 504})`.
- Exponential backoff (NOT jittered): `backoff_base_seconds * 2 ** (attempt - 1)`
  at line 333.
- `max_retries` default = 5 (caller default in `pull_all_payment_summaries`).
- On exhaustion: returns `None` + warning log (lines 321-331); does NOT raise.
- `sleep_fn` is already an injected required parameter at line 296.

You MUST reuse this method as-is from `_sweep_patient_ids`. Do NOT
re-implement backoff.

### Async session + provider-sync-run pattern (mimic verbatim)

From `apps/worker/jobs/backfill_full.py:107-141`:

```python
async with async_session() as session:
    cred_svc = IntegrationCredentialService(session)
    cs = await _get_carestack_client(cred_svc, tenant_id)  # adapt for carestack
    if cs is None:
        log.info("backfill.payment_summary.skipped_credential", tenant_id=str(tenant_id))
        return {"status": "skipped_credential"}
    integration = IntegrationService(session)
    svc = CareStackPaymentSummaryIngestService(session=session, carestack_client=cs)
    run = await integration.open_provider_sync_run(
        tenant_id, provider="carestack", object_scope="payment_summary",
        trigger="backfill_script",
    )
    try:
        imported = await svc.import_payment_summary_for_patients(
            tenant_id, patient_ids,
            sleep_seconds=0.5, commit_every=50, commit=session.commit,
        )
        await integration.close_provider_sync_run(
            tenant_id, sync_run_id=run.id, principal=principal,
            provider="carestack", object_scope="payment_summary",
            status="succeeded", records_total=imported.total,
            records_succeeded=imported.success_count,
            records_failed=imported.error_count,
        )
    except Exception as exc:  # noqa: BLE001
        await integration.close_provider_sync_run(
            tenant_id, sync_run_id=run.id, principal=principal,
            provider="carestack", object_scope="payment_summary",
            status="failed", records_total=0,
            records_succeeded=0, records_failed=0,
            error=str(exc)[:500],
        )
        raise
```

Note: `except Exception` (NOT `BaseException`) — repo convention, never
swallow CancelledError.

### Patient list source

- `packages/identity/repository.py:98-119` — `IdentityRepository.list_source_links_for_dashboard(tenant_id, *, source_system, source_kind, first_seen_from, first_seen_to, limit=200)`.
- For the backfill script, pass `source_system="carestack"`, `source_kind="patient"`, and override `limit` to a cap (default 2000 in the script).

### Tests scaffold (do NOT invent your own style)

Existing factories in `tests/ingest/test_carestack_payment_summary_service.py`:
- `_link(patient_id="9985")` → SimpleNamespace with person_uid, source_id, source_system, source_kind (lines 46-53).
- `_summary_payload(patient_id=9985)` → dict matching CareStack response (lines 55-72).
- `_make_service(*, links=..., summary_side_effect=...)` factory returning `(service, cs_client, ingest_mock, identity_repo_mock)`.
- `_SleepRecorder` class (lines 277-284) — async callable that records waits without blocking. Reuse for throttle assertions.
- `_FakeCareStackApiError` class — for forcing 429/5xx in retry tests.

Wiring pattern: `cs_client.get_payment_summary = AsyncMock(...)`, mocks on
`service._ingest.capture`, `service._identity_repo.list_source_links_for_dashboard`,
`service._identity_repo.find_source_link`.

Sleep injection: `sleep=sleep` passed as kwarg to `pull_all_payment_summaries`
(line 301). Use the same kwarg name in the new `import_payment_summary_for_patients`
and in `_sweep_patient_ids`.

For the accounting test (`tests/ingest/test_carestack_accounting_transaction_service.py`),
`_transaction(...)` factory builds rows; `cs_client.list_accounting_transactions_modified_since = AsyncMock(...)`.

There is NO conftest.py in `tests/ingest/`. Root conftest at `tests/conftest.py`
has `two_tenant_db` for cross-tenant isolation — out of scope here.

## Tasks (TDD — write tests first for each)

### 1. Refactor `CareStackPaymentSummaryIngestService`

In `packages/ingest/carestack_payment_summary_service.py`:

- Extract the per-patient loop (currently at lines 242-272 inside
  `pull_all_payment_summaries`) into a private:
  ```python
  async def _sweep_patient_ids(
      self,
      tenant_id: TenantId,
      patient_ids: Iterable[str],
      *,
      sleep_seconds: float,
      max_retries: int,
      backoff_base_seconds: float,
      sleep_fn: Callable[[float], Awaitable[None]],
      commit_every: int,
      commit: Callable[[], Awaitable[None]] | None,
  ) -> tuple[int, int]:  # (success_count, error_count)
  ```
  - Iterate input patient_ids (no listing — caller resolves the set).
  - Throttle: `await sleep_fn(sleep_seconds)` between patients (skip before first).
  - Fetch via existing `_fetch_summary_with_backoff` (DO NOT touch its logic).
  - On `summary is None`: `error_count += 1`, continue (failure isolation).
  - On success: `await self._ingest.capture(...)` as today; `success_count += 1`.
  - Batch commit: every `commit_every` patients (success OR error), if
    `commit is not None`, `await commit()`. Final `await commit()` at end if any
    work was done.
  - Return `(success_count, error_count)`.

- `pull_all_payment_summaries` keeps its signature; lists linked CareStack
  patient_ids via `self._identity_repo.list_source_links_for_dashboard(...)` as
  today, derives `patient_ids: list[str]`, then delegates to `_sweep_patient_ids`.
  Build `CareStackPaymentSummaryImportOut` from returned counts.

- NEW public method:
  ```python
  async def import_payment_summary_for_patients(
      self,
      tenant_id: TenantId,
      patient_ids: Iterable[str],
      *,
      sleep_seconds: float = 0.5,
      max_retries: int = 5,
      backoff_base_seconds: float = 1.0,
      sleep: Callable[[float], Awaitable[None]] | None = None,
      commit_every: int = 50,
      commit: Callable[[], Awaitable[None]] | None = None,
  ) -> CareStackPaymentSummaryImportOut:
  ```
  - Dedup input (preserve insertion order: `list(dict.fromkeys(patient_ids))`).
  - Resolve `sleep_fn = sleep or asyncio.sleep`.
  - Delegate to `_sweep_patient_ids`. Return `CareStackPaymentSummaryImportOut`.

**Tests** (`tests/ingest/test_carestack_payment_summary_service.py`):
- `_sweep_patient_ids` covers every input patient_id (assert
  `cs_client.get_payment_summary.await_count == len(patient_ids)`).
- Throttle uses injected sleep: `_SleepRecorder.waits` has the expected count
  and values.
- Failure isolation: one patient raises retryable exhaustion → success_count
  decremented, error_count++, sweep continues.
- Commit-per-batch: `commit_mock = AsyncMock()`; with `commit_every=2` over 5
  patients, `commit_mock.await_count == 3` (2 batches of 2 + final flush).
  Without `commit` (None), service does NOT crash.
- `import_payment_summary_for_patients` dedups: `["A","B","A","C","B"]` →
  3 calls.

### 2. Accounting service: collect `imported` patient_ids

In `packages/ingest/carestack_accounting_transaction_service.py`:

- In `import_recent_accounting_transactions` (loop at lines 227-252), build
  `imported_patient_ids: set[str] = set()`.
- After `outcome = await self._capture_transaction(..., patient_id=patient_id)`:
  - If `outcome == "imported" and patient_id is not None`:
    `imported_patient_ids.add(patient_id)`.
  - Do NOT add for "skipped" (no patientId / not linked / non-payment folio).
- Return `CareStackAccountingTransactionImportOut(..., patient_ids=sorted(imported_patient_ids))`.

In `packages/ingest/schemas.py`, add to
`CareStackAccountingTransactionImportOut` (lines 177-191):
```python
patient_ids: list[str] = Field(default_factory=list)
```

**Tests** (`tests/ingest/test_carestack_accounting_transaction_service.py`):
- Three transactions: one imported (PATIENTPAYMENTS, linked, patient_id="9001"),
  one skipped (PATIENTPAYMENTS, no linked patient), one PROCEDURECOMPLETED
  (not a payment, even if linked) → output `patient_ids == ["9001"]` only.
- Two imported rows for the same patient → output has the patient once.
- Empty rows → `patient_ids == []`.

### 3. Wire live signal in scheduled job

`apps/worker/jobs/ingest_scheduled.py` lines 197-212: between the accounting
pull (line 204) and the existing rolling
`import_payment_summary_snapshots(max_patients=50)` call (line 211), insert:

```python
if accounting_transactions.patient_ids:
    await payment_summary_svc.import_payment_summary_for_patients(
        tenant_id,
        accounting_transactions.patient_ids,
        commit=session.commit,
    )
```

KEEP the existing `import_payment_summary_snapshots(max_patients=50)` rolling
sweep — it covers patients who haven't had transactions but whose balance
still drifts. Document this decision in the worker report.

### 4. New backfill script

`infra/scripts/backfill_payment_summary.py` (NEW file):

- CLI flags: `--tenant-id <uuid>`, `--max-patients <int>` (default 2000),
  `--sleep-seconds <float>` (default 0.5), `--commit-every <int>` (default 50),
  `--dry-run` (lists patient_ids it WOULD process, count, exits).
- Opens `async_session()`; mimics the `backfill_full.py:107-141` pattern
  (open/close provider_sync_run with `provider="carestack"`,
  `object_scope="payment_summary"`, `trigger="backfill_script"`).
- Resolves patient_ids via
  `IdentityRepository(session).list_source_links_for_dashboard(tenant_id,
  source_system="carestack", source_kind="patient", limit=max_patients)`,
  derives `[link.source_id for link in links if link.source_id]`.
- Invokes `svc.import_payment_summary_for_patients(tenant_id, patient_ids,
  sleep_seconds=..., commit_every=..., commit=session.commit)`.
- Logs only `patient_id` and counts — NO PHI (no names, no balances).
- Exit code 0 on success; non-zero on credential miss / exception.
- MUST be runnable as `python3 infra/scripts/backfill_payment_summary.py
  --tenant-id <uuid>`. MUST NOT be wired to any HTTP endpoint.

**Tests** (`tests/infra/test_backfill_payment_summary.py` — NEW):
- Cap honored: `max_patients=3` with 10 links → only 3 patient_ids processed.
- `--dry-run` doesn't touch the CareStack client (`AsyncMock.await_count == 0`).
- Sleep is injectable (parametrize the script's main via a kwarg or
  monkeypatch `asyncio.sleep`) — assert mock called.
- CareStack client fully mocked. Test verifies NO real network call.

If the script can't ergonomically accept an injected sleep, design the main
function (e.g. `async def main(args, *, sleep=None, session_factory=None)`) so
tests can inject; the CLI entry calls `main(args)`.

## Hard constraints

- **Tests MUST mock CareStack.** ZERO real API calls in dev/CI. If you need
  to grep — `grep -RIn 'AsyncMock\|MagicMock' tests/ingest/` to see existing
  patterns.
- **Throttle ≥ 0.5s/patient.** Backoff on 429/5xx already in
  `_fetch_summary_with_backoff` — reuse, don't reimplement.
- **CareStack blocked this account ~24h once.** If the real backfill ever
  hits sustained 429 → abort. (Not your concern in this ticket; just don't
  introduce more pressure.)
- **Background script only**, NOT HTTP. Next proxy 30s timeout has burned us
  before with orphaned long runs.
- **Batch commits** (default 50). Never wrap the whole sweep in one
  transaction.
- **No PHI in logs.** patient_id and counts only. No names, DOB, allergies,
  notes, clinical text.
- **`except Exception`, never `except BaseException`.** Repo convention —
  see `feedback_except_exception_only`.
- **Repo language: English** for code, comments, identifiers, log keys,
  error messages, commit messages. Russian only in user-facing UI strings
  (none in this ticket).
- **Do NOT touch `apps/web/lib/msw/handlers.ts`** — unrelated WIP from
  another stream.
- **Do NOT add new migrations.** This ticket is non-schema.
- **Do NOT remove or modify** `import_payment_summary_snapshots(max_patients=50)`
  unless the existing tests explicitly cover removal (they don't). Document
  the decision in the report.

## Definition of done

1. `make lint` clean.
2. `mypy .` clean (new `Callable[..., Awaitable[None]]` signatures pass).
3. `make test` green — including new tests above.
4. `cd packages/db && alembic check` clean (no migration drift).
5. Commit to your worktree branch ONLY (NOT main). Commit message format:
   `ENG-305: throttled payment-summary backfill + live signal + script`.
6. Write `.agents/orchestration/current/reports/ENG-305-worker-report.md` with:
   - task id + Linear URL;
   - role / agent / branch / worktree;
   - touched files list;
   - what changed (one paragraph per major piece);
   - tests added + results;
   - verification commands run + their outcome;
   - risks identified;
   - any blocker / question;
   - suggested next task (probably the follow-up UI ticket);
   - explicit DO-NOT-MERGE conditions (e.g. "do not run real backfill until
     user gives explicit go").
7. Do NOT run the real CareStack backfill — that is a SEPARATE explicit user
   decision after merge.

If you hit something the implementation map didn't predict, STOP and write
`Blocked:` in the report rather than guess. The orchestrator session is
waiting and can answer.

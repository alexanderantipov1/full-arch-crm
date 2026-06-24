# Hybrid Orchestrator + Workflow — Session Kickoff

Paste the **Kickoff prompt** block below into a fresh Claude Code session
(another terminal) to resume Fusion CRM work in the same hybrid pattern.
Update the "Current state" section at the end of each work session so the
next pickup is accurate.

---

## Kickoff prompt (copy from here)

```
/orchestrator

Продолжаем Fusion CRM в режиме гибрид-оркестратора (как в прошлой сессии).

ПАТТЕРН на каждый тикет:
1. Выбираешь именованную mission dir под тикет: .agents/orchestration/<alias>-v1
   (+ runtime dir в ~/.fusion-agent-orchestrator/<hash>/). Общего указателя
   current/ нет — миссии живут параллельно, чистим/закрываем вручную.
2. Workflow PRE-FLIGHT (1-3 Haiku-агента, read-only) — мапят файлы/сигнатуры
   точек врезки. Факты вшиваешь в worker prompt.
3. Бутстрапишь mission spec в .agents/orchestration/<alias>-v1/
   (goal/acceptance/verification/contract/ownership/decision-log).
4. launch_worker.py --workspace worktree --mode print → одобряю → запускаешь
   воркера детачнуто (claude -p --permission-mode acceptEdits в worktree,
   run_in_background). MSW WIP в handlers.ts стэшишь на время launcher,
   возвращаешь после.
5. По завершении воркера — Workflow ADVERSARIAL REVIEW (2-3 Sonnet-лензы:
   correctness / no-PHI-leak / mocking). aggregated_pass=false с реальным
   major/critical → re-dispatch воркера с фидбеком. "false" из-за
   spec-vs-reality формулировки → accept с обоснованием в incidents.md.
6. ВСЕГДА верифицируй на ЖИВЫХ данных, не только mocked-тесты (в прошлой
   сессии живая проверка поймала 2 бага что прошли review).
7. ff-merge в main, verify loop (make lint / mypy / pytest / alembic check
   + apps/web npm lint/tsc/test), push, Linear Done + comment, cleanup
   worktree+branch.

ЖЁСТКОЕ:
- НЕ коммить/пуш/мутации БД без моего явного "go".
- Реальные CareStack/--apply прогоны — отдельное моё подтверждение.
- НЕ трогать apps/web/lib/msw/handlers.ts (чужой data-intelligence WIP).
- prod tenant = 11111111-1111-4111-8111-111111111111.

Прочитай .agents/orchestration/ архивы + Linear ENG-305..311 для контекста,
а также раздел "Current state" в .agents/orchestration/HYBRID_KICKOFF.md.
Жди мою задачу.
```

(end copy)

---

## How the hybrid works (mental model)

- **Workflow** = read-side fan-out (cheap parallel agents): PRE-FLIGHT recon
  BEFORE the worker + ADVERSARIAL REVIEW after. Ephemeral; they do NOT write
  dashboard runtime state.
- **launch_worker.py** = ONE implementation in an isolated git worktree,
  dashboard-visible (runtime.json), Linear-gated, survives a session crash.
  One worker codes sequentially.

Workflow at the edges (fast/cheap), launcher in the center (durable/isolated).

## Operational gotchas (learned the hard way)

- Launch the worker with:
  `cd <worktree> && claude -p --permission-mode acceptEdits "$(cat <prompt>)" > <log> 2>&1`
  via Bash `run_in_background: true`. `launch_worker.py --mode print` shows the
  command + writes runtime files; the actual detached launch is done by hand so
  the worker survives the orchestrator session.
- `pytest` inside a worktree needs `-o pythonpath=.` — the shared `.venv` is
  editable-installed against the source repo, not the worktree, so without it
  pytest imports the un-edited source and never sees the worktree's changes.
- `launch_worker.py` refuses a dirty `--branch-base`. Stash `handlers.ts`
  (+ any local WIP / settings.json model-unpin) before launch; restore after.
- Mission spec lives in repo (`.agents/orchestration/<mission>/`); live runtime
  (runtime.json/board.md/linear-sync.md/runlog.md/prompts/logs) lives under
  `~/.fusion-agent-orchestrator/<repo-hash>/<mission>/`. Repo-hash for this
  checkout: `c2db50910d08`.
- Pre-existing baseline noise to FILTER (not yours): 2 ruff UP037 in
  `packages/interaction/repository.py`; 2 TS errors in
  `apps/web/lib/msw/handlers.ts` (data-intelligence WIP).
- Verify on REAL data, not just mocked tests. Mocked SQL-shape tests pass
  without executing against real CareStack-formatted payloads (e.g. formatted
  phones `(916) 215-4258`), which has hidden two real bugs this session.

## Adversarial-review verdict triage

- `aggregated_pass=true` → proceed to merge.
- `aggregated_pass=false` with a real `major`/`critical` finding → re-dispatch
  the worker on the same branch with a focused fix prompt (round 2). Re-run the
  same review Workflow on the updated diff.
- `aggregated_pass=false` but the "failures" are claim-wording / spec-vs-reality
  / contract-superset (reviewer itself says "not a code bug") → ACCEPT, log the
  rationale in `incidents.md`, merge. The mocking lens (test-quality gate) must
  be clean either way.

## Current state — UPDATE THIS EACH SESSION

**As of 2026-06-02, main HEAD = `5d9de30` (orchestration artifacts uncommitted):**

- **Done + merged:** ENG-305 (payment-summary backfill data path),
  ENG-306 (person-card financial summary UI), ENG-307 (--only-with-payments
  filter), ENG-308 (CareStack origin context), ENG-309 (identity DOB/SSN
  merge hard-block + audit), ENG-310 (per-pid names + PHI panel + household
  links), ENG-311 (un-merge split script + **FLEET `--apply` DONE 2026-06-02**).
- **Data:** ENG-311 fleet un-merge APPLIED on local `:5434` prod-copy — **3,808
  wrong-merged persons split → wrong_merged=0** (canary 50 + 3,758 fleet, 0
  errors, idempotent). 3,809 `identity.person.split` audit rows; persons
  110,042 → 114,334; 1,224 legit same-human multi-pid preserved (incl. Gaiane
  `5758e85c`, both pids). Pre-apply backup:
  `~/fusion-backups/fusion_5434_pre-eng311-apply_20260602T005726Z.dump` (131 MB,
  PG16). 2,549 patients have payment-summary snapshots; 25 CareStack providers.
- **Test baseline:** backend pytest ~957 passing; apps/web vitest ~78 passing;
  mypy clean (~306 files).
- **OPEN:**
  1. (opt.) GIN / expression index on `raw_event.payload` phone+email to turn
     the household candidate query from a ~60K-row seq-scan into an index
     lookup.
  2. **ENG-312 now MORE relevant** — retroactive `identity.person.dob/ssn`
     backfill from latest CareStack payload. Post-split, NEW persons carry
     bucket dob/ssn but ~110K legacy/surviving persons stay NULL. The ENG-309
     veto reads `person.dob/ssn` (currently NULL globally → veto soft-tiers).
     Backfill uniformly; sequencing after the split is clean.
  3. Orchestration artifacts from the fleet-apply mission (new `current/` spec,
     archived `eng-310-person-card-identity-v1`, this kickoff edit, report) are
     UNCOMMITTED — commit on operator go.
- **Local dev:** Next.js web on http://127.0.0.1:3000 (MSW disabled,
  proxies to API); FastAPI on http://127.0.0.1:8000 with
  `--reload --reload-dir apps --reload-dir packages` (auto-picks code changes).
  Use `127.0.0.1`, never `localhost` (IPv6/IPv4 trap).

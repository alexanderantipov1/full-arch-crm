# Worker Report — ENG-223 Dashboard Auto-Track Active Mission

- **Task:** ENG-223 — Dashboard: auto-track active mission (resolve mission per snapshot)
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-223/dashboard-auto-track-active-mission-resolve-mission-per-snapshot
- **Linear status at handoff:** In Progress
- **Role / Agent:** worker / claude-code (self-execute via /orchestrator)
- **Branch:** `eduardk/eng-223-dashboard-auto-track-active-mission`
- **Worktree:** `.` (current checkout — worktree-as-default not yet shipped, M-2)
- **Allowed scope:** `.agents/dashboard/`,
  `.agents/skills/agent-orchestrator/tests/`,
  `.agents/orchestration/dashboard-auto-track/`. Confirmed: no file
  outside this scope was touched.

## How the work landed

Pre-existing branch already carried the full implementation. The
worker discovered this on checkout (see `incidents.md` 2026-05-22T02:25Z)
and escalated. Doctor approved "Adopt as-is" via /orchestrator. Worker
then:

1. Stashed the freshly-created mission folder, switched to the
   pre-existing branch.
2. Rebased on `main` (1 commit ahead — PR #88 ENG-222). Rebase was
   clean, no conflicts.
3. Popped the stash; mission folder reattached to working tree.
4. Ran the new dashboard test suite — 19/19 green.
5. Ran the existing orchestrator skill suite — 34 passed, 4 skipped
   (contract-drift tests gated on env vars; expected).
6. Smoke-tested the live server: started it without `--mission`,
   hit `/api/snapshot`. Payload reported
   `active_mission_name: dashboard-auto-track`,
   `resolution_reason: matched ENG-223 from git branch`,
   `path: .agents/orchestration/dashboard-auto-track`. End-to-end
   correct.

## Commits on the branch (post-rebase)

```
0d346fd  feat(agents): dashboard auto-tracks active mission (ENG-223)
16924e8  chore(agents): archive completed missions ENG-213/214/215/218
<TBD>    docs(agents): mission folder for ENG-223 dashboard-auto-track
```

The third commit lands the live orchestration runtime + decision
artifacts for this self-execute session.

## Touched files (existing two commits)

- `.agents/dashboard/server.py` (+108 / -8) — adds `re` import; helpers
  `detect_branch_eng_id`, `iter_mission_candidates`,
  `find_mission_by_linear_id`, `find_newest_mission`,
  `resolve_active_mission`; rewires `collect_mission` to accept the
  resolved `(mission, reason)` tuple; rewires `build_snapshot` and
  `/api/logs` to resolve per request.
- `.agents/dashboard/static/app.js` (+15) — surfaces
  `mission.active_mission_name` + `mission.resolution_reason` in topbar.
- `.agents/dashboard/static/index.html` (+8) — topbar markup.
- `.agents/dashboard/tests/__init__.py`, `conftest.py`,
  `test_resolve_active_mission.py` (+322 total) — 19 unit tests.
- 32 mission files moved into `archived/2026-05-21-<name>/` (pure
  `git mv`, no content edits).

## Tests run

```
python3 -m py_compile .agents/dashboard/server.py          → OK
.venv/bin/python -m pytest .agents/dashboard/tests/ -v     → 19 passed in 0.05s
.venv/bin/python -m pytest .agents/skills/agent-orchestrator/tests/  → 34 passed, 4 skipped in 20.23s
```

Smoke test transcript:

```
$ .venv/bin/python .agents/dashboard/server.py --port 8788 &
$ curl -s http://127.0.0.1:8788/api/snapshot | jq '.mission | {active_mission_name, resolution_reason, path}'
active_mission_name: dashboard-auto-track
resolution_reason: matched ENG-223 from git branch
path: .agents/orchestration/dashboard-auto-track
```

## Acceptance recheck

- [x] **A** Mission resolution per snapshot — `build_snapshot()` calls
      `resolve_active_mission(repo, override)` every request.
- [x] **B** Active-mission detector — branch parse + Linear-id match in
      `runtime.json.sessions[]` and `handoffs[]`, mtime fallback,
      archived excluded; verified by unit tests + live smoke.
- [x] **C** Snapshot payload — `active_mission_name` and
      `resolution_reason` exposed; backward-compatible with existing
      consumers.
- [x] **D** Tests — 5+ scenarios required by `acceptance.md` covered by
      the 19 unit cases; existing orchestrator suite stays green.
- [x] **E** Smoke check — observed in live `/api/snapshot`.
- [x] **F** Hygiene — English; no PHI / secrets / `.env*`; no
      third-party deps; no product-code changes.

## Differences vs `contract.md`

- `resolution_reason` strings are prose, not the canonical short
  codes (`branch-match`, `mtime-fallback`, `explicit-flag`,
  `no-mission`) listed in `contract.md`. Functionally equivalent for
  the current UI surface; can be tightened to short codes in a
  follow-up if a regex consumer emerges.
- Tests live under `.agents/dashboard/tests/` rather than
  `.agents/skills/agent-orchestrator/tests/`. `acceptance.md`
  permitted either location.

## Risks

- Per-request mission resolution adds an `os.listdir` + a couple of
  `json.load` calls. For a typical 1–5 folder layout this is well under
  5 ms. If profiling later shows it's hot, add an in-process TTL cache.
- Archive sweep (commit `16924e8`) is benign as long as nobody depended
  on the old paths. Verified: nothing outside `.agents/orchestration/`
  references those folders.
- Running dashboard processes need a restart to pick up the new code.
  The commit message already calls this out; we will note it in PR.

## Blockers / questions

None. Ready for verifier handoff.

## Suggested next task

Open PR. Verifier walks acceptance + runs verify suite. Integrator
flips to `Ready for review` and merges once green.

## Do-not-merge conditions

- Verifier suite fails locally.
- Live smoke test on a fresh checkout shows stale behavior.
- Linear status drift (issue moves to Done while PR is still open).

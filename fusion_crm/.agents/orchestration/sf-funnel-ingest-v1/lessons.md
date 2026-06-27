# Lessons — sf-funnel-ingest-v1

- A repair script's `commit` must be injectable (caller-owned unit of
  work). A test that lets library code commit a shared fixture session
  persists the fixture seed into the dev DB and breaks the whole suite
  via unique constraints — the failure shows up in OTHER tests, far
  from the cause.
- Real-DB assertions in shared databases must be membership-based
  (`seeded_id in result`), never whole-set equality — the surrounding
  data is not empty.
- Watermark cursors over provider feeds REQUIRE ascending order at the
  provider query; `DESC + LIMIT` silently drops the oldest pending
  changes once a burst exceeds the limit.
- Watermark alone does not stop raw duplication: the overlap window
  re-reads rows every tick (10-min overlap / 90-s tick ≈ 7 re-captures
  per change). A capture-level change-guard is required even where the
  watermark exists (treatment service proved it: ENG-324 watermark, yet
  ~70x raw duplication).
- `os.environ.setdefault` in test modules is a global side effect that
  poisons lazily-built engines for the rest of the run.
- Push mission branches to origin at every checkpoint. The ENG-371..382
  chain existed only locally; when packfiles were truncated by a
  disk-full event, seven commits' history (not content) was lost.
  A pushed branch would have made recovery a one-line fetch.
- Do not run heavy DB repairs (millions of deletes) with <10% disk
  free; Postgres WAL churn plus macOS swap can push the volume to
  the edge where APFS starts truncating unrelated writes.

## 2026-06-10 — dev-up.sh supervisor vs process surgery (ENG-384)

- `infra/scripts/dev-up.sh` supervises API/Web/Worker with 3s respawn
  loops and can run orphaned for days. Killing a supervised child does
  not stop it; duplicate supervisors create duplicate arq workers and
  duplicate ingest ticks (fed the ENG-381 duplicate pile).
- Killing the arq child is the canonical worker code reload (arq has no
  --reload); the supervisor respawns it on the current checkout.
- Always `pgrep -fl dev-up.sh` before local process surgery.
- Canonical rules added to `infra/CLAUDE.md` § "dev-up.sh (local dev
  supervisor)".

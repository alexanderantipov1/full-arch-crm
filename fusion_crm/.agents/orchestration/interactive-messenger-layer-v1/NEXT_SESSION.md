# Next Session — Start Here (Interactive Messenger Layer, ENG-433)

**Goal for the next session:** light testing on the merged layer, then begin the
**production bring-up** (ENG-442).

## State (as of 2026-06-15)
- Blocks A–H **DONE** and **merged to `eng-425`** via PR #152 (Codex-reviewed,
  2 rounds; all blocking + non-blocking fixed). Linear ENG-434..441 = Done.
- Proven **live** on real Mattermost: outbound post, full rule→outbox→post
  pipeline, signed inbound (typed message), agent approve→annotation.
- 5 real bugs were caught (mocks missed them) and fixed pre-merge.

## Read first
1. `docs/integrations/mattermost/RUNBOOK.md` — how it works + test checklist + prod plan.
2. `docs/decisions/ADR-0006-interactive-messenger-layer.md` — the decision.
3. `infra/docker/mattermost/README.md` — local bring-up.
4. This mission's `runlog.md` — the full chronological story incl. the 5 bugs.

## Git state to reconcile (do this first)
- `origin/eng-425` has the merged messenger layer; **local `eng-425` is behind** —
  `git fetch && git checkout eng-425 && git pull`.
- The local working tree still carries an **uncommitted full-fidelity slice**
  (apps/api/routers/persons.py, apps/web/*, packages/integrations/provider_links.py,
  apps/api/dependencies.py `get_provider_link_service`, etc.) — that belongs to the
  eng-425 full-fidelity work, NOT the messenger layer. Commit it separately on eng-425.
- The merged remote branch `eng-433-interactive-messenger-layer` can be deleted.
- These docs (RUNBOOK + this file) were committed on a small docs branch off
  origin/eng-425 — merge/rebase as needed.

## Testing pass (new session)
Bring up the local stack (`--profile chat`), confirm Mattermost is up (Rosetta on),
then run the RUNBOOK §4.4 checklist end-to-end against the dev DB. The bot +
outgoing webhook from the prior session persist in the Docker volumes, but the
bot token / webhook token may need re-reading from the dev DB credentials (or
re-create + re-store). Restart the arq worker after any code change.

## Production bring-up (ENG-442) — first moves
1. Resolve open decisions #2 (version pin), #3 (host + chat.* TLS), #4 (prod DB),
   #6 (retention) — see RUNBOOK §5.3. Ask the doctor where needed.
2. Confirm **single alembic head** on the deploy branch + a working
   `alembic upgrade head` against the prod DB (RUNBOOK §5.2). Reconcile any
   cross-epic migration heads (lead-attribution eng-447 may add some).
3. Confirm a prod worker runtime actually runs the drains (email's
   `drain_outbound_queue` is paused in prod per ENG-172 — same constraint).
4. Follow `docs/DEPLOYMENT_RULES.md`; keep prod infra in its own PR.

## Also queued
- **ENG-443 (D2):** wire the 3 remaining events to chat (call-sites in the ticket).
- Frontend Zod `ProviderSchema` += `mattermost`.

## Local stack
Mattermost containers (`mattermost`, `mattermost-db`) may still be running under
profile `chat`. Stop with:
`docker compose -f infra/docker/docker-compose.yml --profile chat stop mattermost mattermost-db`
(data persists in volumes).

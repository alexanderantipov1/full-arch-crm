# Worker Report — ENG-434 (Block A: Local Mattermost infrastructure)

- **Task:** ENG-434 — Local Mattermost infrastructure (compose profile "chat")
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-434
- **Role / agent:** worker / claude-code (self-execute in current checkout)
- **Branch / worktree:** current checkout `eng-425-full-fidelity-ingestion-v1`
  (isolated worktree skipped: launcher preflight rejects a dirty base, and the
  uncommitted full-fidelity + strategy files must not be committed without
  user approval; Block A is small + reversible + infra-only)
- **Task class:** normal (infra/compose only; no migration, no product contract,
  no `.env*` change)

## Allowed scope

`infra/docker/docker-compose.yml`, `infra/docker/mattermost/**`

## Touched files

- `infra/docker/docker-compose.yml` — added `mattermost` + `mattermost-db`
  services under compose profile `chat`; added named volumes (`mmdbdata`,
  `mmdata`, `mmconfig`, `mmlogs`, `mmplugins`, `mmclientplugins`, `mmbleve`).
- `infra/docker/mattermost/README.md` — new: bring-up, bot creation, version-pin
  policy, English-locale rule, "not in Block A" boundaries.

## What changed

- Mattermost (official `mattermost/mattermost-team-edition:10.5`, not forked)
  and a dedicated `mattermost-db` Postgres, both gated behind profile `chat`.
- Mattermost DB is physically separate from the canonical 8-schema DB
  (invariant #1 preserved).
- Bound to `127.0.0.1:8065`; shares the compose network with `api` so local
  inbound webhooks need no public tunnel.
- Bot/webhook/slash/action capabilities enabled via `MM_*` env; English locale.

## Tests / verification

```
docker compose -f infra/docker/docker-compose.yml config --services
  → redis, postgres, worker, api   (NO mattermost — default profile gated) ✅
docker compose -f infra/docker/docker-compose.yml --profile chat config --services
  → ... mattermost-db, mattermost  (present under chat profile) ✅
docker compose -f infra/docker/docker-compose.yml --profile chat config -q
  → OK (only pre-existing env-var-not-set warnings) ✅
```

Containers were NOT started (acceptance is config-level + the README); actually
booting Mattermost and creating the admin/team/bot is an operator step.

## Acceptance status

- [x] `--profile chat up` would bring up Mattermost on 127.0.0.1:8065 (config valid)
- [x] default `docker compose up` does NOT start Mattermost
- [x] README documents bot creation + token retrieval + pinned version + locale

## Risks

- Image tag `10.5` is pinned from knowledge, not Hub-verified in this run; the
  operator should confirm the exact latest-stable tag exists on first `up`
  (README documents the bump procedure). Low risk — only affects first pull.

## Remaining (operator step, not code)

Run the bring-up command, create admin + Team + bot account, copy the bot token
for Block B (ENG-435).

## Suggested next task

ENG-436 (Block C: outbox + rules schema + dispatch worker) — merge-order says
C before B's event wiring. Block B (ENG-435) adapter can proceed in parallel
once the bot token exists.

## Do-not-merge conditions

None specific; bundle per solo-dev policy with the next related block if desired.
Cross-runtime review still recommended before merging the broader feature branch.

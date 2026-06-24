# Fusion CRM — developer convenience commands
# Use the .env file at the repo root.

SHELL := /bin/bash
ENV_FILE ?= .env

.PHONY: help install fmt lint typecheck test verify verify-deploy verify-full \
        verify-alembic-heads \
        up down logs ps build \
        db-upgrade db-downgrade db-revision \
        api worker sync-local shell \
        web web-install web-test web-lint \
        backup restore preflight-prod

help:
	@echo "Targets:"
	@echo "  install        Install Python deps into local venv"
	@echo "  fmt / lint     Format / lint with ruff"
	@echo "  typecheck      Run mypy across packages + apps"
	@echo "  test           Run pytest"
	@echo "  verify         Run lint + typecheck + tests (CI gate)"
	@echo "  verify-alembic-heads  Assert exactly one alembic head (race guard)"
	@echo "  up / down      Start / stop docker stack"
	@echo "  logs / ps      Tail / list docker services"
	@echo "  build          Rebuild docker images"
	@echo "  db-upgrade     Run alembic upgrade head"
	@echo "  db-revision M='msg'  Create alembic autogenerate migration"
	@echo "  api / worker   Run service locally (without docker)"
	@echo "  sync-local     Drain provider pulls until local DB is caught up"
	@echo "  backup / restore  Run backup or restore script"

# ----- Local dev -----
install:
	python3.12 -m venv .venv && \
	. .venv/bin/activate && \
	pip install -U pip && \
	pip install -e ".[dev]"

fmt:
	ruff format .
	ruff check --fix .

lint:
	ruff check .

typecheck:
	mypy packages apps

test:
	python -m pytest -q

# CI gate — runs the same checks as the GitHub Actions `verify` job in
# .github/workflows/deploy-prod.yml. Lint + typecheck + the deploy-
# critical drift tests (cheap; subset of pytest). Full `pytest` is
# gated separately (`make verify-full`) until the rest of the test
# suite is unblocked (ENG-123 tenant fixture). Do not promote a
# `verify-full` call to CI without fixing collection first.
verify: lint typecheck verify-deploy verify-alembic-heads

# Single-head guard (ENG-545). Asserts the alembic revision graph has
# exactly one head, so a concurrent-migration race (two PRs branching a
# migration off the same parent and both merging to `main`) is caught
# here — red CI before merge — instead of on the prod `alembic upgrade
# head` job. Offline: `alembic heads` reads the versions directory only,
# never connects to a DB. Effective together with branch protection's
# "require branch up to date before merge", which forces the trailing PR
# to rebase and thus surface both heads in its branch. See
# docs/DEPLOYMENT_RULES.md ("Concurrent alembic heads").
verify-alembic-heads:
	@cd packages/db && \
	out="$$(alembic heads 2>/dev/null)" ; \
	count="$$(printf '%s\n' "$$out" | grep -c .)" ; \
	if [ "$$count" != "1" ] ; then \
		echo "ERROR: expected exactly 1 alembic head, found $$count:" >&2 ; \
		alembic heads >&2 ; \
		echo "" >&2 ; \
		echo "Resolve by rejoining the heads into one merge revision:" >&2 ; \
		echo "  cd packages/db && alembic merge heads -m 'merge <a>+<b>'" >&2 ; \
		exit 1 ; \
	fi ; \
	echo "alembic single-head OK ($$(printf '%s' "$$out" | head -n1))"

# Deploy-critical drift tests only. Fast (sub-second), no network,
# no DB. Catches Settings ↔ production.env.reference ↔ deploy script
# drift (Phase 2 + ENG-174 §A) before deploy, and the deploy-prod
# traffic-primary filter contract (ENG-179) against the workflow YAML.
verify-deploy:
	python -m pytest \
		tests/core/test_env_reference_matches_settings.py \
		tests/core/test_traffic_primary_filter.py \
		-q

verify-full: lint typecheck test

# Run the production deploy preflight read-only checks against the
# live GCP project (ENG-174 §A). Operator should run this before
# any manual `deploy_cloud_run.sh` invocation. CI runs it
# automatically between auth and alembic-migrate.
preflight-prod:
	./infra/scripts/preflight_prod.sh

# ----- Docker -----
up:
	docker compose --env-file $(ENV_FILE) -f infra/docker/docker-compose.yml up -d

down:
	docker compose -f infra/docker/docker-compose.yml down

logs:
	docker compose -f infra/docker/docker-compose.yml logs -f --tail=200

ps:
	docker compose -f infra/docker/docker-compose.yml ps

build:
	docker compose -f infra/docker/docker-compose.yml build

# ----- Migrations -----
db-upgrade:
	cd packages/db && alembic upgrade head

db-downgrade:
	cd packages/db && alembic downgrade -1

db-revision:
	cd packages/db && alembic revision --autogenerate -m "$(M)"

# ----- Services (local, no docker) -----
api:
	uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

worker:
	arq apps.worker.main.WorkerSettings

# Drain CareStack + Salesforce pulls until the local DB is caught up
# (ENG-330). Calls the same run_local_sync the /dev/sync-local button
# uses. Local-dev only. Pass flags via ARGS, e.g.
#   make sync-local ARGS="--provider carestack --max-pages 40"
sync-local:
	python -m infra.scripts.sync_local $(ARGS)

dev-up:
	./infra/scripts/dev-up.sh

dev-check:
	./infra/scripts/dev-up.sh --check

shell:
	python -i -c "import asyncio; from packages.db.session import async_session"

# ----- Frontend (apps/web) -----
web-install:
	cd apps/web && npm install && npx msw init public --save

web:
	cd apps/web && npm run dev

web-test:
	cd apps/web && npm run test

web-lint:
	cd apps/web && npm run lint && npm run typecheck

# ----- Backups -----
backup:
	./infra/scripts/backup.sh

restore:
	./infra/scripts/restore.sh $(BACKUP)

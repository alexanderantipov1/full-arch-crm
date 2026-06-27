lint: ruff + mypy (packages/identity, new migration)
tests: tests/identity (+ new shared-contact + unique-kind cases)
migration: alembic upgrade head + downgrade on a real test PostgreSQL; drift check

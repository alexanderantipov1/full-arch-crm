from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_session_import_registers_all_domain_models() -> None:
    env = os.environ.copy()
    env.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://test:test@127.0.0.1:5432/test",
    )
    env.setdefault(
        "DATABASE_URL_SYNC",
        "postgresql+psycopg://test:test@127.0.0.1:5432/test",
    )
    env.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
    env.setdefault("SECRET_KEY", "test-secret")

    script = (
        "import packages.db.session\n"
        "from packages.db.base import Base\n"
        "assert 'actor.actor' in Base.metadata.tables\n"
        "assert 'identity.match_candidate' in Base.metadata.tables\n"
    )

    subprocess.run(  # noqa: S603 - fixed interpreter and inline test script.
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        check=True,
    )

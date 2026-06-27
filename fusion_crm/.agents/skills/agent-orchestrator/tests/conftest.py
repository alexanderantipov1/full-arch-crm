"""Common fixtures for orchestrator launcher tests.

Tests run hermetically: a fake `codex` / `claude` shim is injected via PATH
so the launcher can be exercised without the real CLIs. Mission state lives
in `tmp_path` per test; never write to a live `.agents/orchestration/<mission>/`.
"""

# ruff: noqa: S108
# `/tmp/x` below is a never-touched argparse-Namespace placeholder; tests
# override `mission` with `tmp_path` via the `make_args` factory.

from __future__ import annotations

import importlib
import importlib.util
import os
from argparse import Namespace
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
LAUNCHER_PATH = SCRIPTS_DIR / "launch_worker.py"
RUN_WAVE_PATH = SCRIPTS_DIR / "run_wave.py"
STATUS_WAVE_PATH = SCRIPTS_DIR / "status_wave.py"


@pytest.fixture(scope="session")
def launcher_module():
    """Import `launch_worker.py` as a module without executing main()."""
    spec = importlib.util.spec_from_file_location("launch_worker", LAUNCHER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _runtime_home(tmp_path: Path, monkeypatch):
    """Isolate FUSION_AGENT_RUNTIME_HOME under tmp_path for every test.

    Setting the env var to `tmp_path` means `paths.mission_runtime_dir(name)`
    resolves to `tmp_path/name`. The `mission_dir` fixture creates
    `tmp_path/mission`, so the runtime dir for the default mission lines up
    with the spec dir — pre-M-1 tests that wrote runtime files alongside
    decision artifacts continue to work without code changes. Tests that
    want explicit separation can use the `runtime_dir` fixture below.
    """
    monkeypatch.setenv("FUSION_AGENT_RUNTIME_HOME", str(tmp_path))


@pytest.fixture
def mission_dir(tmp_path: Path) -> Path:
    """Fresh empty mission spec folder per test (decision artifacts live here)."""
    mission = tmp_path / "mission"
    mission.mkdir()
    return mission


# Forward-compat alias: tests that want to be explicit about the spec / runtime
# split use these names. Both default to the same path so legacy tests keep
# passing.
@pytest.fixture
def mission_spec_dir(mission_dir: Path) -> Path:
    return mission_dir


@pytest.fixture
def runtime_dir(mission_dir: Path) -> Path:
    """Where runtime telemetry (runtime.json, runlog.md, board.md, ...) lives.

    Same path as `mission_dir` by default thanks to the `_runtime_home`
    autouse fixture; tests that pre-date the M-1 split read this fixture
    transparently.
    """
    return mission_dir


@pytest.fixture
def make_args():
    """Build an argparse.Namespace with sane defaults; override per test."""

    def _make(**overrides):
        defaults = dict(
            mission=Path("/tmp/x"),
            runtime="codex",
            role="worker",
            mode="print",
            task_id="T-1",
            linear_id="ENG-213",
            linear_url="https://linear.app/x/y",
            linear_title="Smoke",
            linear_status="In Progress",
            prompt="echo ok",
            prompt_file=None,
            worktree=str(Path.cwd()),
            branch="main",
            worker_name="",
            phase="assigned",
            reason="Test launch.",
            risk="low",
            note="Test note.",
            codex_sandbox="workspace-write",
            codex_bypass_approvals=False,
            codex_full_auto=False,
            claude_permission_mode="default",
            tmux_name=None,
            # M-2 / ENG-225 — workspace defaults. Tests default to
            # self-execute so they don't try to provision a real git
            # worktree against the tmp mission folder. Tests that
            # exercise --workspace worktree pass overrides.
            workspace="self",
            allow_self_execute=True,
            scope="tiny",
            branch_base="main",
        )
        defaults.update(overrides)
        return Namespace(**defaults)

    return _make


@pytest.fixture
def fake_runtime_dir(tmp_path: Path) -> Path:
    """Create a directory holding fake `codex` and `claude` executables.

    Each shim prints START/END markers around a short sleep so tests can
    assert log content was written after the launcher exited.
    """
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    body = (
        "#!/bin/bash\n"
        'echo "SHIM_START pid=$$ ppid=$PPID name=$0"\n'
        "sleep 2\n"
        'echo "SHIM_END pid=$$"\n'
    )
    for name in ("codex", "claude"):
        path = shim_dir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
    return shim_dir


@pytest.fixture
def fake_runtime_path(monkeypatch, fake_runtime_dir):
    """Prepend fake runtime dir to PATH for the duration of the test."""
    new_path = f"{fake_runtime_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    monkeypatch.setenv("PATH", new_path)
    return fake_runtime_dir


@pytest.fixture
def launcher_subprocess_env(fake_runtime_path):
    """Env dict suitable for subprocess.Popen calls that need the fake runtime."""
    env = os.environ.copy()
    env["PATH"] = os.environ["PATH"]  # already monkeypatched above
    return env


def pytest_configure(config):
    """Register skill-local marks so pytest does not warn about them."""
    config.addinivalue_line(
        "markers",
        "codex_contract: contract-drift test against installed codex CLI "
        "(env-gated via CODEX_CONTRACT_TESTS=1)",
    )
    config.addinivalue_line(
        "markers",
        "claude_contract: contract-drift test against installed claude CLI "
        "(env-gated via CLAUDE_CONTRACT_TESTS=1)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip contract-drift tests unless the corresponding env flag is set."""
    skip_codex = pytest.mark.skip(reason="CODEX_CONTRACT_TESTS not set")
    skip_claude = pytest.mark.skip(reason="CLAUDE_CONTRACT_TESTS not set")
    for item in items:
        if "codex_contract" in item.keywords and not os.environ.get("CODEX_CONTRACT_TESTS"):
            item.add_marker(skip_codex)
        if "claude_contract" in item.keywords and not os.environ.get("CLAUDE_CONTRACT_TESTS"):
            item.add_marker(skip_claude)

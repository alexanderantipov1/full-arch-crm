"""Centralised path resolution for orchestrator runtime layout.

Mission decision artifacts (goal.md, acceptance.md, contract.md,
ownership.yaml, decision-log.md, lessons.md, incidents.md, reports/)
live in the repository at `.agents/orchestration/<mission_id>/`.

Mission runtime telemetry (runtime.json, runlog.md, board.md,
linear-sync.md, prompts/, logs/, worktrees/) lives outside the repo at
`<runtime_root>/<mission_id>/`.

The default runtime root is `~/.fusion-agent-orchestrator/<repo-hash>/`
where `<repo-hash>` is a stable SHA over the resolved repo path. The
env var `FUSION_AGENT_RUNTIME_HOME`, when set, overrides the entire
root (no `<repo-hash>` appended) so tests can monkeypatch into
`tmp_path` cleanly.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
RUNTIME_HOME_ENV = "FUSION_AGENT_RUNTIME_HOME"
DEFAULT_RUNTIME_HOME_NAME = ".fusion-agent-orchestrator"
ORCHESTRATION_DIR_NAME = "orchestration"


def repo_hash(repo_root: Path | None = None) -> str:
    target = (repo_root or REPO_ROOT).resolve()
    return hashlib.sha256(str(target).encode("utf-8")).hexdigest()[:12]


def runtime_root(repo_root: Path | None = None) -> Path:
    explicit = os.environ.get(RUNTIME_HOME_ENV)
    if explicit:
        return Path(explicit).resolve()
    return Path.home() / DEFAULT_RUNTIME_HOME_NAME / repo_hash(repo_root)


def mission_spec_dir(mission_id: str, repo_root: Path | None = None) -> Path:
    base = (repo_root or REPO_ROOT).resolve()
    return base / ".agents" / ORCHESTRATION_DIR_NAME / mission_id


def mission_runtime_dir(mission_id: str, repo_root: Path | None = None) -> Path:
    return runtime_root(repo_root) / mission_id


def worktree_dir(mission_id: str, task_id: str, repo_root: Path | None = None) -> Path:
    return mission_runtime_dir(mission_id, repo_root) / "worktrees" / task_id


def mission_id_from_spec_path(spec_path: Path) -> str:
    """Extract the mission_id from a spec-dir path. The basename is the id."""
    return Path(spec_path).name

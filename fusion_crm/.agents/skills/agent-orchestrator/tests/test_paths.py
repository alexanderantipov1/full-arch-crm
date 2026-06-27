"""Unit tests for orchestrator path helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def paths_module():
    """Import paths.py fresh per test so env-state at import time is clean."""
    spec = importlib.util.spec_from_file_location("paths_under_test", SCRIPTS_DIR / "paths.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_default_runtime_root_uses_repo_hash(monkeypatch, paths_module):
    monkeypatch.delenv(paths_module.RUNTIME_HOME_ENV, raising=False)
    root = paths_module.runtime_root()
    assert root.name == paths_module.repo_hash()
    assert root.parent.name == paths_module.DEFAULT_RUNTIME_HOME_NAME
    assert root.parent.parent == Path.home()


def test_env_override_wins_over_default(monkeypatch, tmp_path, paths_module):
    monkeypatch.setenv(paths_module.RUNTIME_HOME_ENV, str(tmp_path))
    assert paths_module.runtime_root() == tmp_path.resolve()


def test_env_override_does_not_append_repo_hash(monkeypatch, tmp_path, paths_module):
    monkeypatch.setenv(paths_module.RUNTIME_HOME_ENV, str(tmp_path / "isolated"))
    root = paths_module.runtime_root()
    assert root == (tmp_path / "isolated").resolve()
    assert paths_module.repo_hash() not in root.parts


def test_repo_hash_is_stable_under_symlink(tmp_path, paths_module):
    real = tmp_path / "real-repo"
    real.mkdir()
    link = tmp_path / "linked-repo"
    link.symlink_to(real)
    assert paths_module.repo_hash(real) == paths_module.repo_hash(link)


def test_repo_hash_differs_for_different_roots(tmp_path, paths_module):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert paths_module.repo_hash(a) != paths_module.repo_hash(b)


def test_mission_runtime_dir_is_under_runtime_root(monkeypatch, tmp_path, paths_module):
    monkeypatch.setenv(paths_module.RUNTIME_HOME_ENV, str(tmp_path))
    assert paths_module.mission_runtime_dir("alpha") == tmp_path.resolve() / "alpha"


def test_mission_spec_dir_is_under_repo(tmp_path, paths_module):
    fake_repo = tmp_path / "fake-repo"
    fake_repo.mkdir()
    spec = paths_module.mission_spec_dir("alpha", repo_root=fake_repo)
    assert spec == fake_repo.resolve() / ".agents" / "orchestration" / "alpha"


def test_worktree_dir_layout(monkeypatch, tmp_path, paths_module):
    monkeypatch.setenv(paths_module.RUNTIME_HOME_ENV, str(tmp_path))
    wt = paths_module.worktree_dir("alpha", "T-1")
    assert wt == tmp_path.resolve() / "alpha" / "worktrees" / "T-1"


def test_worktree_dir_is_under_mission_runtime_dir(monkeypatch, tmp_path, paths_module):
    """Compositional invariant: worktree paths must nest under mission_runtime_dir."""
    monkeypatch.setenv(paths_module.RUNTIME_HOME_ENV, str(tmp_path))
    mrd = paths_module.mission_runtime_dir("alpha")
    wt = paths_module.worktree_dir("alpha", "T-1")
    assert mrd in wt.parents, f"{wt} must nest under {mrd}"


def test_mission_id_from_spec_path_uses_basename(paths_module):
    p = Path("/a/b/c/.agents/orchestration/my-mission")
    assert paths_module.mission_id_from_spec_path(p) == "my-mission"


def test_repo_hash_short_length(paths_module):
    h = paths_module.repo_hash()
    assert len(h) == 12
    assert all(c in "0123456789abcdef" for c in h)

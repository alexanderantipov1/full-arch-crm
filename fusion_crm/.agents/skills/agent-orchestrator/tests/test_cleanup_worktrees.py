"""Unit + integration tests for cleanup_worktrees.py."""

# ruff: noqa: S603, S607
# Tests intentionally invoke `git` via subprocess against tmp repos.

from __future__ import annotations

import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def cleanup_module():
    spec = importlib.util.spec_from_file_location(
        "cleanup_worktrees_under_test", SCRIPTS_DIR / "cleanup_worktrees.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_list_worktrees_finds_nested_task_dirs(tmp_path, cleanup_module):
    rt = tmp_path / "rt"
    (rt / "mission-a" / "worktrees" / "T-1").mkdir(parents=True)
    (rt / "mission-a" / "worktrees" / "T-2").mkdir(parents=True)
    (rt / "mission-b" / "worktrees" / "T-3").mkdir(parents=True)
    (rt / "mission-c" / "no-worktrees-dir").mkdir(parents=True)
    found = sorted(p.name for p in cleanup_module.list_worktrees(rt))
    assert found == ["T-1", "T-2", "T-3"]


def test_list_worktrees_empty_when_runtime_missing(tmp_path, cleanup_module):
    assert cleanup_module.list_worktrees(tmp_path / "absent") == []


def test_mission_archived_matches_suffix(tmp_path, cleanup_module, monkeypatch):
    fake_archived = tmp_path / "archived"
    fake_archived.mkdir()
    (fake_archived / "2026-05-22-my-mission").mkdir()
    monkeypatch.setattr(cleanup_module, "ARCHIVED_DIR", fake_archived)
    assert cleanup_module.mission_archived("my-mission") is True
    assert cleanup_module.mission_archived("other-mission") is False


def test_dry_run_lists_candidates_without_removal(tmp_path, cleanup_module, monkeypatch):
    """`--dry-run` (default) prints candidates and does not remove anything."""
    rt = tmp_path / "rt"
    wt = rt / "missionX" / "worktrees" / "T-1"
    wt.mkdir(parents=True)

    monkeypatch.setattr(cleanup_module, "classify", lambda p: {
        "path": p, "mission_id": "missionX", "task_id": "T-1",
        "branch": "eng-x-t-1", "archived": True, "merged": True,
        "eligible": True, "reason": "test-eligible",
    })

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cleanup_module.main(["--runtime-root", str(rt)])
    out = buf.getvalue()

    assert rc == cleanup_module.EXIT_OK
    assert "ELIGIBLE" in out
    assert "test-eligible" in out
    # Worktree dir still exists — dry-run does not delete.
    assert wt.is_dir()


def test_force_without_apply_is_refused(tmp_path, cleanup_module, capsys):
    rc = cleanup_module.main(["--force", "--runtime-root", str(tmp_path)])
    assert rc == cleanup_module.EXIT_GUARDRAIL
    captured = capsys.readouterr()
    assert "--force requires --apply" in captured.err


def test_apply_with_declined_confirmation_keeps_worktree(
    tmp_path, cleanup_module, monkeypatch
):
    rt = tmp_path / "rt"
    wt = rt / "missionX" / "worktrees" / "T-1"
    wt.mkdir(parents=True)

    monkeypatch.setattr(cleanup_module, "classify", lambda p: {
        "path": p, "mission_id": "missionX", "task_id": "T-1",
        "branch": "eng-x-t-1", "archived": True, "merged": True,
        "eligible": True, "reason": "eligible-for-apply-test",
    })
    monkeypatch.setattr(cleanup_module, "confirm", lambda _prompt: False)
    monkeypatch.setattr(cleanup_module, "remove_worktree", lambda _p: True)

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cleanup_module.main(["--apply", "--runtime-root", str(rt)])

    assert rc == cleanup_module.EXIT_DECLINED
    assert wt.is_dir()


def test_apply_with_accepted_confirmation_removes_worktree(
    tmp_path, cleanup_module, monkeypatch
):
    rt = tmp_path / "rt"
    wt = rt / "missionX" / "worktrees" / "T-1"
    wt.mkdir(parents=True)

    classify_calls = {"count": 0}

    def fake_classify(p):
        classify_calls["count"] += 1
        return {
            "path": p, "mission_id": "missionX", "task_id": "T-1",
            "branch": "eng-x-t-1", "archived": True, "merged": True,
            "eligible": True, "reason": "eligible",
        }

    remove_calls = []

    def fake_remove(p):
        remove_calls.append(p)
        return True

    monkeypatch.setattr(cleanup_module, "classify", fake_classify)
    monkeypatch.setattr(cleanup_module, "confirm", lambda _prompt: True)
    monkeypatch.setattr(cleanup_module, "remove_worktree", fake_remove)

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cleanup_module.main(["--apply", "--runtime-root", str(rt)])

    assert rc == cleanup_module.EXIT_OK
    assert remove_calls == [wt]


def test_skip_when_branch_not_merged(tmp_path, cleanup_module, monkeypatch):
    rt = tmp_path / "rt"
    wt = rt / "missionX" / "worktrees" / "T-1"
    wt.mkdir(parents=True)

    monkeypatch.setattr(cleanup_module, "classify", lambda p: {
        "path": p, "mission_id": "missionX", "task_id": "T-1",
        "branch": "eng-x-t-1", "archived": True, "merged": False,
        "eligible": False, "reason": "branch unmerged",
    })

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cleanup_module.main(["--apply", "--runtime-root", str(rt)])

    assert rc == cleanup_module.EXIT_DECLINED  # no removals happened
    assert "SKIP" in buf.getvalue()
    assert wt.is_dir()


def test_force_can_remove_unmerged_with_two_confirmations(
    tmp_path, cleanup_module, monkeypatch
):
    rt = tmp_path / "rt"
    wt = rt / "missionX" / "worktrees" / "T-1"
    wt.mkdir(parents=True)

    monkeypatch.setattr(cleanup_module, "classify", lambda p: {
        "path": p, "mission_id": "missionX", "task_id": "T-1",
        "branch": "eng-x-t-1", "archived": True, "merged": False,
        "eligible": False, "reason": "unmerged but archived",
    })
    # Both confirmation prompts return True.
    monkeypatch.setattr(cleanup_module, "confirm", lambda _prompt: True)
    removed = []
    monkeypatch.setattr(cleanup_module, "remove_worktree", lambda p: removed.append(p) or True)

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cleanup_module.main(
            ["--apply", "--force", "--runtime-root", str(rt)]
        )

    assert rc == cleanup_module.EXIT_OK
    assert removed == [wt]
    assert "ELIGIBLE-WITH-FORCE" in buf.getvalue()

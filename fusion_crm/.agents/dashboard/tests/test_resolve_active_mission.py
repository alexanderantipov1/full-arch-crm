"""Tests for the active-mission resolver in `.agents/dashboard/server.py`.

The resolver decides which `.agents/orchestration/<mission>/` folder the
dashboard renders on each request. Resolution order:

  1. explicit `--mission` override;
  2. git branch ENG-\\d+ matched against runtime.json sessions/handoffs;
  3. newest mtime under `.agents/orchestration/` (excluding `archived/`);
  4. nothing.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest


def _make_repo(tmp_path: Path) -> Path:
    """Lay down the minimal `.agents/orchestration/` skeleton."""
    (tmp_path / ".agents" / "orchestration").mkdir(parents=True)
    return tmp_path


def _make_mission(
    repo: Path,
    name: str,
    *,
    sessions_linear_id: str | None = None,
    handoff_linear_id: str | None = None,
) -> Path:
    folder = repo / ".agents" / "orchestration" / name
    folder.mkdir(parents=True, exist_ok=True)
    runtime = {"mission_id": name, "sessions": [], "handoffs": []}
    if sessions_linear_id:
        runtime["sessions"].append(
            {"id": "s1", "linear_issue_id": sessions_linear_id, "status": "running"}
        )
    if handoff_linear_id:
        runtime["handoffs"].append(
            {"id": "h1", "linear_issue_id": handoff_linear_id, "status": "accepted"}
        )
    (folder / "runtime.json").write_text(json.dumps(runtime), encoding="utf-8")
    return folder


def _set_mtime(path: Path, when: float) -> None:
    os.utime(path, (when, when))


def _patch_branch(monkeypatch, server, branch: str | None) -> None:
    """Stub `detect_branch_eng_id` to return what we want, since shelling
    out to git inside the test repo would be fragile."""
    if branch is None:
        monkeypatch.setattr(server, "detect_branch_eng_id", lambda _repo: None)
        return
    import re

    match = re.search(r"ENG-\d+", branch, re.IGNORECASE)
    eng_id = match.group(0).upper() if match else None
    monkeypatch.setattr(server, "detect_branch_eng_id", lambda _repo: eng_id)


# -- explicit override -------------------------------------------------------


def test_explicit_override_wins_even_when_other_missions_exist(
    server, tmp_path, monkeypatch
):
    repo = _make_repo(tmp_path)
    pinned = _make_mission(repo, "pinned-mission")
    _make_mission(repo, "newer-mission", sessions_linear_id="ENG-100")
    _patch_branch(monkeypatch, server, "eduardk/eng-100-foo")

    resolved, reason = server.resolve_active_mission(repo, pinned)

    assert resolved == pinned
    assert "explicit" in reason.lower()


def test_explicit_override_preserved_when_path_does_not_exist(
    server, tmp_path, monkeypatch
):
    repo = _make_repo(tmp_path)
    nonexistent = repo / ".agents" / "orchestration" / "ghost-mission"
    _patch_branch(monkeypatch, server, None)

    resolved, reason = server.resolve_active_mission(repo, nonexistent)

    assert resolved == nonexistent
    assert "explicit" in reason.lower()


# -- git branch detection ---------------------------------------------------


def test_resolve_by_branch_matches_session_linear_id(
    server, tmp_path, monkeypatch
):
    repo = _make_repo(tmp_path)
    target = _make_mission(repo, "target-mission", sessions_linear_id="ENG-219")
    _make_mission(repo, "other-mission", sessions_linear_id="ENG-218")
    _patch_branch(monkeypatch, server, "eduardk/eng-219-carestack-foo")

    resolved, reason = server.resolve_active_mission(repo, None)

    assert resolved == target
    assert "ENG-219" in reason
    assert "branch" in reason.lower()


def test_resolve_by_branch_matches_handoff_linear_id(
    server, tmp_path, monkeypatch
):
    repo = _make_repo(tmp_path)
    target = _make_mission(repo, "handoff-mission", handoff_linear_id="ENG-300")
    _make_mission(repo, "other-mission", sessions_linear_id="ENG-301")
    _patch_branch(monkeypatch, server, "eduardk/eng-300-something")

    resolved, reason = server.resolve_active_mission(repo, None)

    assert resolved == target
    assert "ENG-300" in reason


def test_branch_eng_id_case_insensitive(server, tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    target = _make_mission(repo, "case-mission", sessions_linear_id="ENG-500")
    _patch_branch(monkeypatch, server, "feature/eng-500-lowercase-branch")

    resolved, _reason = server.resolve_active_mission(repo, None)

    assert resolved == target


# -- mtime fallback ---------------------------------------------------------


def test_falls_back_to_newest_mtime_when_branch_has_no_eng_id(
    server, tmp_path, monkeypatch
):
    repo = _make_repo(tmp_path)
    older = _make_mission(repo, "older")
    newer = _make_mission(repo, "newer")
    _set_mtime(older, time.time() - 3600)
    _set_mtime(newer, time.time())
    _patch_branch(monkeypatch, server, "main")

    resolved, reason = server.resolve_active_mission(repo, None)

    assert resolved == newer
    assert "newest" in reason.lower()
    assert "newer" in reason


def test_falls_back_to_mtime_when_branch_eng_id_does_not_match(
    server, tmp_path, monkeypatch
):
    repo = _make_repo(tmp_path)
    _make_mission(repo, "old", sessions_linear_id="ENG-100")
    newer = _make_mission(repo, "fresh", sessions_linear_id="ENG-200")
    _set_mtime(repo / ".agents" / "orchestration" / "old", time.time() - 3600)
    _set_mtime(newer, time.time())
    _patch_branch(monkeypatch, server, "eduardk/eng-999-not-in-runtime-files")

    resolved, reason = server.resolve_active_mission(repo, None)

    assert resolved == newer
    assert "ENG-999" in reason
    assert "newest" in reason.lower()


# -- archived exclusion -----------------------------------------------------


def test_excludes_archived_directory_from_mtime_fallback(
    server, tmp_path, monkeypatch
):
    repo = _make_repo(tmp_path)
    archived_root = repo / ".agents" / "orchestration" / "archived"
    archived_root.mkdir()
    archived_mission = archived_root / "2026-05-19-foo"
    archived_mission.mkdir()
    (archived_mission / "runtime.json").write_text("{}", encoding="utf-8")
    _set_mtime(archived_mission, time.time())

    live = _make_mission(repo, "live-mission")
    _set_mtime(live, time.time() - 3600)
    _patch_branch(monkeypatch, server, None)

    resolved, _reason = server.resolve_active_mission(repo, None)

    assert resolved == live


def test_excludes_archived_from_linear_id_lookup(
    server, tmp_path, monkeypatch
):
    repo = _make_repo(tmp_path)
    archived_root = repo / ".agents" / "orchestration" / "archived"
    archived_root.mkdir()
    archived_with_match = archived_root / "old"
    archived_with_match.mkdir()
    (archived_with_match / "runtime.json").write_text(
        json.dumps(
            {
                "sessions": [
                    {"id": "x", "linear_issue_id": "ENG-77", "status": "running"}
                ]
            }
        ),
        encoding="utf-8",
    )
    _make_mission(repo, "live", sessions_linear_id="ENG-99")
    _patch_branch(monkeypatch, server, "feature/eng-77-foo")

    resolved, reason = server.resolve_active_mission(repo, None)

    # ENG-77 only lives in archived/, so we should NOT match it; instead fall
    # back to the live mission via mtime.
    assert resolved is not None
    assert resolved.name == "live"
    assert "ENG-77" in reason
    assert "newest" in reason.lower()


# -- empty state ------------------------------------------------------------


def test_returns_none_when_no_missions_exist(server, tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    _patch_branch(monkeypatch, server, "main")

    resolved, reason = server.resolve_active_mission(repo, None)

    assert resolved is None
    assert "no missions" in reason.lower()


def test_returns_none_when_orchestration_dir_missing(
    server, tmp_path, monkeypatch
):
    repo = tmp_path  # no .agents/orchestration/ at all
    _patch_branch(monkeypatch, server, None)

    resolved, reason = server.resolve_active_mission(repo, None)

    assert resolved is None
    assert "no missions" in reason.lower()


# -- collect_mission integration --------------------------------------------


def test_collect_mission_exposes_active_name_and_reason(server, tmp_path):
    repo = _make_repo(tmp_path)
    mission = _make_mission(repo, "my-mission", sessions_linear_id="ENG-42")

    payload = server.collect_mission(mission, "matched ENG-42 from git branch", repo)

    assert payload["active_mission_name"] == "my-mission"
    assert payload["resolution_reason"] == "matched ENG-42 from git branch"
    assert payload["configured"] is True
    assert payload["exists"] is True


def test_collect_mission_handles_none(server, tmp_path):
    payload = server.collect_mission(None, "no missions found anywhere", tmp_path)

    assert payload["active_mission_name"] is None
    assert payload["resolution_reason"] == "no missions found anywhere"
    assert payload["configured"] is False
    assert payload["exists"] is False
    assert "no missions found anywhere" in payload["empty_state"]


@pytest.mark.parametrize(
    "branch,expected",
    [
        ("eduardk/eng-219-foo", "ENG-219"),
        ("feature/ENG-1-a", "ENG-1"),
        ("eng-42-bar", "ENG-42"),
        ("main", None),
        ("eduardk/no-id-here", None),
        ("", None),
    ],
)
def test_detect_branch_eng_id_parses_known_shapes(
    server, monkeypatch, branch, expected
):
    # Stub run_git used inside detect_branch_eng_id to return the given branch.
    monkeypatch.setattr(server, "run_git", lambda _repo, *_args: branch)
    assert server.detect_branch_eng_id(Path(".")) == expected


# -- process control --------------------------------------------------------


def test_parse_ownership_rules_extracts_task_paths_and_no_touch(server):
    payload = server.parse_ownership_rules(
        """
mission: demo
tasks:
  ENG-1:
    owner: codex
    paths:
      - packages/ops/
      - apps/api/router.py
shared_no_touch:
  - .agents/dashboard/  # owned by another session
"""
    )

    assert payload["tasks"]["ENG-1"]["paths"] == ["packages/ops/", "apps/api/router.py"]
    assert payload["shared_no_touch"] == [".agents/dashboard/"]


def test_parse_git_status_line_handles_stripped_first_line(server):
    assert server.parse_git_status_line("M .agents/dashboard/server.py") == {
        "status": "M",
        "path": ".agents/dashboard/server.py",
        "raw": "M .agents/dashboard/server.py",
    }
    assert server.parse_git_status_line(" M .agents/dashboard/app.js") == {
        "status": "M",
        "path": ".agents/dashboard/app.js",
        "raw": " M .agents/dashboard/app.js",
    }


def test_collect_process_control_classifies_changed_paths(server):
    git = {
        "status_entries": [
            {"status": "M", "path": "packages/ops/service.py"},
            {"status": "M", "path": ".agents/dashboard/server.py"},
            {"status": "M", "path": "README.md"},
            {"status": "M", "path": ".agents/orchestration/demo/goal.md"},
        ]
    }
    mission = {
        "active_mission_name": "demo",
        "path": ".agents/orchestration/demo",
        "runtime": {
            "sessions": [
                {
                    "task_id": "ENG-1",
                    "status": "running",
                    "linear_issue_id": "ENG-1",
                    "linear_issue_url": "https://linear.app/example/ENG-1",
                }
            ]
        },
        "ownership_rules": {
            "tasks": {"ENG-1": {"paths": ["packages/ops/"]}},
            "shared_no_touch": [".agents/dashboard/"],
        },
    }

    result = server.collect_process_control(git, mission)
    categories = {item["path"]: item["category"] for item in result["changed"]}

    assert categories["packages/ops/service.py"] == "authorized"
    assert categories[".agents/dashboard/server.py"] == "no_touch"
    assert categories["README.md"] == "unmanaged"
    assert categories[".agents/orchestration/demo/goal.md"] == "mission_state"
    assert result["gate"] == "blocked"
    assert result["requires_orchestrator"] is True


def test_collect_process_control_flags_missing_linear(server):
    git = {"status_entries": []}
    mission = {
        "active_mission_name": "demo",
        "path": ".agents/orchestration/demo",
        "runtime": {"sessions": [{"task_id": "ENG-2", "status": "running"}]},
        "ownership_rules": {"tasks": {}, "shared_no_touch": []},
    }

    result = server.collect_process_control(git, mission)

    assert result["gate"] == "blocked"
    assert result["missing_linear_tasks"] == ["ENG-2"]
    assert result["requires_orchestrator"] is True

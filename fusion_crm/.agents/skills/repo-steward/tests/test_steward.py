"""Unit tests for the Repo Steward pure helpers.

These cover the reversibility-classification logic without touching a real
git repo: branch parsing, merged-branch filtering (the safety boundary), the
ahead/behind parse, and the approval-queue builder.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import steward  # noqa: E402


def test_parse_ahead_behind_normal():
    assert steward.parse_ahead_behind("0\t16") == (0, 16)
    assert steward.parse_ahead_behind("3 2") == (3, 2)


def test_parse_ahead_behind_garbage():
    assert steward.parse_ahead_behind("") == (0, 0)
    assert steward.parse_ahead_behind("oops") == (0, 0)
    assert steward.parse_ahead_behind("1 2 3") == (0, 0)


def test_parse_branch_list_marks_current_and_worktree():
    raw = "* main\n  feature-a\n+ wt-branch\n"
    parsed = steward.parse_branch_list(raw)
    assert (True, "main") in parsed
    assert (False, "feature-a") in parsed
    assert (False, "wt-branch") in parsed


def test_parse_branch_list_skips_detached():
    raw = "* (HEAD detached at abc123)\n  real-branch\n"
    names = [n for _, n in steward.parse_branch_list(raw)]
    assert names == ["real-branch"]


def test_deletable_excludes_current_protected_and_worktree():
    merged = "* main\n  eng-100\n  eng-101\n+ eng-wt\n  master\n"
    deletable = steward.deletable_merged_branches(merged, worktree_branches={"eng-wt"})
    # current (main via *), protected (master), and the +worktree branch are excluded
    assert deletable == ["eng-100", "eng-101"]


def test_deletable_respects_explicit_worktree_set():
    merged = "  eng-200\n  eng-201\n"
    deletable = steward.deletable_merged_branches(merged, worktree_branches={"eng-201"})
    assert deletable == ["eng-200"]


def test_build_queue_fast_forward_push():
    q = steward.build_queue(ahead=2, behind=0, remote_merged=[], live_worktrees_to_remove=[])
    assert len(q) == 1
    assert q[0]["kind"] == "push"
    assert q[0]["command"] == "git push origin main"


def test_build_queue_diverged_is_not_a_plain_push():
    q = steward.build_queue(ahead=2, behind=1, remote_merged=[], live_worktrees_to_remove=[])
    assert q[0]["kind"] == "push-diverged"
    assert "push origin main" not in q[0]["command"]


def test_build_queue_remote_and_worktree_items(tmp_path):
    worktree_path = tmp_path / "wt-a"
    q = steward.build_queue(
        ahead=0,
        behind=0,
        remote_merged=["eng-500", "eng-501"],
        live_worktrees_to_remove=[str(worktree_path)],
    )
    kinds = [i["kind"] for i in q]
    assert kinds == ["remote-branch-delete", "remote-branch-delete", "worktree-remove"]
    assert q[0]["command"] == "git push origin --delete eng-500"
    assert q[2]["command"] == f"git worktree remove {worktree_path}"


def test_build_queue_empty_when_clean():
    assert steward.build_queue(0, 0, [], []) == []

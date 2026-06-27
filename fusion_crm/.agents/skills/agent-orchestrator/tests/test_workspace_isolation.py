"""Integration tests: parallel worker worktree isolation.

Spins up a tmp git repo, calls `_provision_worktree` twice with
distinct task ids, and asserts each worker's worktree is on its own
branch with no file-stomping bleed.
"""

# ruff: noqa: S603, S607
# Tests intentionally invoke `git` via subprocess against tmp repos.

from __future__ import annotations

import subprocess

import pytest


@pytest.fixture
def tmp_git_repo(tmp_path):
    """Create a minimal tmp git repo with an initial commit on `main`.

    Repo lives at `tmp_path/repo` so the test can place the runtime
    home at `tmp_path/runtime` without polluting the repo's git status.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "test"], check=True)
    (repo / "seed.txt").write_text("seed\n")
    subprocess.run(["git", "-C", str(repo), "add", "seed.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True)
    return repo


def test_two_parallel_workers_get_distinct_branches(
    monkeypatch, tmp_path, tmp_git_repo, launcher_module
):
    """Worker A and Worker B on the same mission, same Linear id, distinct tasks → distinct branches."""
    runtime_home = tmp_path / "runtime"
    runtime_home.mkdir()
    monkeypatch.setenv("FUSION_AGENT_RUNTIME_HOME", str(runtime_home))

    wt_a, branch_a = launcher_module._provision_worktree(
        repo=tmp_git_repo,
        mission_id="m",
        task_id="TASK-A",
        linear_id="ENG-225",
        branch_base="main",
        session_id="sessAAA",
    )
    wt_b, branch_b = launcher_module._provision_worktree(
        repo=tmp_git_repo,
        mission_id="m",
        task_id="TASK-B",
        linear_id="ENG-225",
        branch_base="main",
        session_id="sessBBB",
    )

    assert wt_a != wt_b, "worktree paths must differ"
    assert branch_a != branch_b, "branch names must differ"
    assert branch_a == "eng-225-task-a"
    assert branch_b == "eng-225-task-b"
    # Both worktrees must contain the seed file (forked off main).
    assert (wt_a / "seed.txt").read_text() == "seed\n"
    assert (wt_b / "seed.txt").read_text() == "seed\n"


def test_file_edits_do_not_bleed_between_worktrees(
    monkeypatch, tmp_path, tmp_git_repo, launcher_module
):
    """A new file inside Worker A's worktree must NOT appear in Worker B's."""
    runtime_home = tmp_path / "runtime"
    runtime_home.mkdir()
    monkeypatch.setenv("FUSION_AGENT_RUNTIME_HOME", str(runtime_home))

    wt_a, _ = launcher_module._provision_worktree(
        repo=tmp_git_repo, mission_id="m", task_id="TASK-A",
        linear_id="ENG-225", branch_base="main", session_id="aaaaaa",
    )
    wt_b, _ = launcher_module._provision_worktree(
        repo=tmp_git_repo, mission_id="m", task_id="TASK-B",
        linear_id="ENG-225", branch_base="main", session_id="bbbbbb",
    )

    (wt_a / "worker-a-output.txt").write_text("A wuz here")

    # Worker B must NOT see Worker A's edit.
    assert not (wt_b / "worker-a-output.txt").exists()
    # Canonical repo working tree must NOT see Worker A's edit.
    assert not (tmp_git_repo / "worker-a-output.txt").exists()


def test_collision_suffix_when_branch_already_exists(
    monkeypatch, tmp_path, tmp_git_repo, launcher_module
):
    """If the natural branch name exists, append session-id suffix."""
    runtime_home = tmp_path / "runtime"
    runtime_home.mkdir()
    monkeypatch.setenv("FUSION_AGENT_RUNTIME_HOME", str(runtime_home))

    # First worker claims `eng-225-task-a`.
    wt1, branch1 = launcher_module._provision_worktree(
        repo=tmp_git_repo, mission_id="m", task_id="TASK-A",
        linear_id="ENG-225", branch_base="main", session_id="first1abcdef",
    )
    assert branch1 == "eng-225-task-a"

    # Second worker on the same task id (re-launch) — must get a suffix.
    wt2, branch2 = launcher_module._provision_worktree(
        repo=tmp_git_repo, mission_id="m2", task_id="TASK-A",
        linear_id="ENG-225", branch_base="main", session_id="secondb2c3d4",
    )
    assert branch2.startswith("eng-225-task-a-")
    assert branch2 != branch1
    assert wt1 != wt2


def test_dirty_base_allows_worktree_by_default(
    monkeypatch, tmp_path, tmp_git_repo, launcher_module
):
    """A dirty canonical checkout must NOT block worktree creation.

    Worktrees are checked out from the committed base ref and are isolated
    from the canonical working tree, so a dirty canonical checkout is the
    expected parallel-work state.
    """
    runtime_home = tmp_path / "runtime"
    runtime_home.mkdir()
    monkeypatch.setenv("FUSION_AGENT_RUNTIME_HOME", str(runtime_home))

    (tmp_git_repo / "dirty.txt").write_text("uncommitted")

    wt_path, branch = launcher_module._provision_worktree(
        repo=tmp_git_repo,
        mission_id="m",
        task_id="TASK-A",
        linear_id="ENG-225",
        branch_base="main",
        session_id="dirty00000",
    )
    assert wt_path.is_dir()
    assert branch == "eng-225-task-a"
    # The dirty file lived only in the canonical tree, not the new worktree.
    assert not (wt_path / "dirty.txt").exists()


def test_dirty_base_refuses_worktree_when_require_clean(
    monkeypatch, tmp_path, tmp_git_repo, launcher_module
):
    """Opt-in strict gate still refuses to launch off a dirty base."""
    runtime_home = tmp_path / "runtime"
    runtime_home.mkdir()
    monkeypatch.setenv("FUSION_AGENT_RUNTIME_HOME", str(runtime_home))

    (tmp_git_repo / "dirty.txt").write_text("uncommitted")

    with pytest.raises(SystemExit, match="uncommitted"):
        launcher_module._provision_worktree(
            repo=tmp_git_repo,
            mission_id="m",
            task_id="TASK-A",
            linear_id="ENG-225",
            branch_base="main",
            session_id="dirty00000",
            require_clean_base=True,
        )

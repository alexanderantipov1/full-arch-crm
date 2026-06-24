"""Contract drift tests against the real codex / claude CLIs.

These tests are env-gated so CI without the binaries does not fail. Set
`CODEX_CONTRACT_TESTS=1` or `CLAUDE_CONTRACT_TESTS=1` to opt in.

The tests guard against silent CLI changes (the exact failure mode that
produced the 2026-05-20 incident — codex removed `--ask-for-approval` and the
launcher kept using it).
"""

# ruff: noqa: S603
# Subprocess invocations target locally-installed CLIs (codex, claude) whose
# absolute paths are resolved via shutil.which before each test.

from __future__ import annotations

import shutil
import subprocess

import pytest


def _help_text(binary: str, subcommand: str | None = None) -> str:
    cmd = [binary]
    if subcommand:
        cmd.append(subcommand)
    cmd.append("--help")
    return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout


@pytest.mark.codex_contract
def test_codex_exec_supports_cd_and_sandbox_flags():
    if shutil.which("codex") is None:
        pytest.skip("codex binary not on PATH")
    text = _help_text("codex", "exec")
    assert "--cd" in text, "codex exec lost `--cd` — launcher will need a refit"
    assert "--sandbox" in text, "codex exec lost `--sandbox` — launcher will need a refit"


@pytest.mark.codex_contract
def test_codex_exec_no_longer_has_ask_for_approval():
    """The flag the launcher used to emit must remain gone — regression guard."""
    if shutil.which("codex") is None:
        pytest.skip("codex binary not on PATH")
    text = _help_text("codex", "exec")
    assert "--ask-for-approval" not in text, (
        "codex exec re-introduced `--ask-for-approval`; "
        "decide whether to reintroduce launcher support or rely on bypass flag"
    )


@pytest.mark.codex_contract
def test_codex_exec_supports_dangerous_bypass_flag():
    if shutil.which("codex") is None:
        pytest.skip("codex binary not on PATH")
    text = _help_text("codex", "exec")
    assert "--dangerously-bypass-approvals-and-sandbox" in text, (
        "codex exec lost `--dangerously-bypass-approvals-and-sandbox` — "
        "`--codex-bypass-approvals` is now broken"
    )


@pytest.mark.claude_contract
def test_claude_supports_print_and_permission_mode_flags():
    if shutil.which("claude") is None:
        pytest.skip("claude binary not on PATH")
    text = _help_text("claude")
    assert "-p" in text or "--print" in text
    assert "--permission-mode" in text

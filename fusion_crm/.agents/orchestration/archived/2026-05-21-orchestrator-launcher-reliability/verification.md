# Verification

## Pre-merge checks

1. **Background-launch survival smoke.**
   - Run the launcher with `--runtime codex --mode background` and a tiny
     prompt that prints a sentinel string.
   - Within 1 second the launcher process exits 0.
   - Within 3 seconds the log file has non-zero size and contains the
     sentinel.
   - Repeat for `--runtime claude-code`.
2. **Static drift guard.**
   - `grep -RIn "ask-for-approval" .agents/skills/agent-orchestrator/scripts .agents/skills/agent-orchestrator/SKILL.md .claude/commands`
     returns nothing. Audit references in `.agents/strategy/`, mission folder,
     and the test suite (which intentionally asserts the flag's absence) are
     intentional and excluded from this check.
   - `codex exec --help` shows no `--ask-for-approval` flag — confirm
     that the launcher only uses flags listed in the current help output.
3. **Test suite.**
   - `pytest .agents/skills/agent-orchestrator/tests/ -v` is green.
   - With `CODEX_CONTRACT_TESTS=1 CLAUDE_CONTRACT_TESTS=1` set, contract
     drift tests pass.
4. **Docs check.**
   - `SKILL.md` and `.claude/commands/orchestrator.md` snippet examples no
     longer reference `--ask-for-approval`.
   - `tests/README.md` (or equivalent) documents how to run the new suite.

## Worker report contract

Worker report at `reports/TASK-A-worker-report.md` must include:

- task id and Linear id;
- branch and worktree;
- changed files;
- the verification commands actually run and their results;
- risks and follow-ups;
- do-not-merge conditions if any.

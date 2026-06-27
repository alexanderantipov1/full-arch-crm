# Architecture Radar

Themes we have observed and decided **not** to action yet. Each entry
records what the idea is, where it comes from, why we are deferring, and
the signal that would flip it from "defer" to "now".

This file is append-only by convention; promote an entry to
`CANDIDATE_MISSIONS.md` when the trigger fires.

## Active deferrals

### Plugin slots / provider abstraction layer

- **Source:** ComposioHQ/agent-orchestrator design — explicit interfaces
  for `Runtime`, `Agent`, `Workspace`, `Tracker`, `SCM`, `Notifier`,
  `Terminal` providers.
- **What it would look like for us:** thin abstraction around
  `agent provider` (codex | claude-code), `runtime provider`
  (background | tmux), `tracker provider` (linear), `workspace provider`
  (worktree), `scm provider` (github), surfaced via config rather than
  hardcoded in launcher scripts.
- **Why we are deferring:** We have exactly one of each today. Abstraction
  without diversity is overhead — interface design choices we make now
  will be wrong by the time we add a second provider, and refactoring is
  cheaper than maintaining premature abstractions.
- **Trigger to promote:** a second tracker (e.g. GitHub Projects, Jira)
  OR a second SCM (e.g. GitLab) OR a second agent type beyond
  codex/claude-code lands in the same week. Two of those at once = it's
  time.
- **Estimated effort when triggered:** medium. Pulling provider details
  out of `launch_worker.py` is mechanical once we know the second
  provider's shape.

### CI / PR review-comment reactions auto-feedback

- **Source:** ComposioHQ — CI failure, review comments, and "changes
  requested" automatically flow back to the orchestrator dashboard so the
  human partner can re-dispatch workers without context-switching to
  GitHub.
- **What it would look like for us:** a control-plane process that polls
  Linear and GitHub (or accepts webhooks), surfaces `Verification failed:`
  / `Changes requested:` / `CI failed:` markers in the dashboard, and
  optionally generates a follow-up worker prompt with the relevant
  context attached.
- **Why we are deferring:** solo dev with at most one or two parallel
  PRs in review. Manually tabbing between GitHub, Linear, and the
  dashboard is annoying but cheap. Building a webhook listener, secret
  management for GitHub deliveries, and the dispatcher is expensive.
- **Trigger to promote:** three or more concurrent active PRs in review
  for more than 24 hours. At that point the tab-switching cost crosses
  the build cost.
- **Estimated effort when triggered:** medium-large. Local
  webhook-receiver process, secret management, dashboard plumbing,
  follow-up-prompt generator.

### Mandatory PR-per-worker

- **Source:** ComposioHQ — each worker owns a worktree + branch + PR;
  one worker, one PR.
- **What it would look like for us:** every worker assignment must end
  with a PR, no exceptions. Bundling multiple workers into one PR is not
  allowed.
- **Why we are deferring:** existing memory `feedback_pr_granularity`
  (Solo dev — bundle related plan tickets into one PR; chain migrations
  in same branch) deliberately favors bundling for the current team size.
  ComposioHQ assumes a multi-developer team where atomic PRs aid review;
  we do not benefit from that yet.
- **Trigger to promote:** a second non-AI reviewer regularly engages with
  PRs OR a regression occurs where bundling masked a faulty change. Until
  then, bundling stays.
- **Estimated effort when triggered:** small (policy change in
  `.claude/commands/orchestrator.md` and the orchestrator skill), but the
  cultural shift requires real reason.

### Terminal multiplexer / interactive worker attach

- **Source:** ComposioHQ — workers run inside tmux/Zellij with native
  attach for the human.
- **What it would look like for us:** beyond the existing `--mode tmux`
  flag, a richer attach surface: per-worker named sessions, layout
  presets (log-pane + status-pane + control-pane), key bindings to send
  prompts back to the agent.
- **Why we are deferring:** the M-3 mission (Process Supervision And
  Granular Activity States) ships `--attach <session-id>` as tail-only,
  which covers 90 % of "what is this worker doing?" questions. Full
  multiplexer integration is polish.
- **Trigger to promote:** the orchestrator regularly runs more than three
  workers in parallel AND `--attach` tail-only proves insufficient (e.g.
  workers stall waiting for input that the human cannot send back).
- **Estimated effort when triggered:** medium. Building on the existing
  tmux mode is incremental.

## How to use this file

- When a Strategy session surfaces an idea that is **not now**, write the
  entry here, not in `CANDIDATE_MISSIONS.md`.
- When a trigger fires for an entry above, **delete** the entry from this
  file and create the corresponding candidate mission in
  `CANDIDATE_MISSIONS.md`. The radar is for things we are not yet doing;
  promoted entries graduate.
- Entries here are not exhaustive — they capture only what we have
  consciously evaluated and consciously deferred. Other ideas die in
  conversation transcripts.

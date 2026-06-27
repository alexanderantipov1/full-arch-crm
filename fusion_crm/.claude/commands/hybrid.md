Start (or resume) Fusion CRM work as the hybrid orchestrator.

Do this now, in order:

1. Read `.agents/orchestration/HYBRID_KICKOFF.md` in full — it defines the
   hybrid pattern, the operational gotchas, the adversarial-review triage
   rules, and the "Current state" snapshot.
2. Load the orchestrator role: follow `.agents/skills/agent-orchestrator/SKILL.md`
   and the orchestration CLAUDE.md / AGENTS.md files it points to.
3. Read the "Current state" section of HYBRID_KICKOFF.md so you know what is
   already merged (ENG-305..311) and what is still open (fleet un-merge,
   optional GIN index, optional ENG-312).
4. Skim the relevant Linear tickets (ENG-305..311) for context if the task
   touches that area.

Then run every ticket in the HYBRID pattern from HYBRID_KICKOFF.md:
archive prev mission → Workflow pre-flight (Haiku, read-only) → mission spec
→ launch_worker.py worktree (print → I approve → detached background) →
Workflow adversarial review (Sonnet lenses) → verify on REAL data, not just
mocked tests → ff-merge → verify loop → push → Linear Done → cleanup.

Hard rules (non-negotiable):
- NEVER commit, push, or mutate the DB without my explicit "go".
- Real CareStack pulls / `--apply` runs need a SEPARATE explicit "go".
- Do NOT touch `apps/web/lib/msw/handlers.ts` (another stream's WIP).
- prod tenant = 11111111-1111-4111-8111-111111111111.

After you've loaded context, summarize the current state in 3-4 lines and
wait for my task. Do not start implementing anything yet.

#!/usr/bin/env bash
# Apply the hardened merge gate on `main` as a GitHub repository ruleset
# (ENG-545, "variant B" merge/deploy hardening — Layer 1).
#
# This is the server-enforced half of the migration-race / merge gate. It
# requires CI green on the exact head, forces branches up to date before
# merge (so a concurrent alembic head surfaces in the trailing PR's own CI),
# dismisses stale approvals on push, requires a PR (see review-count note
# below), and blocks force-push / deletion of `main`. No bypass actors.
#
# Required approvals = 0 (NOT 1). The platform is single-operator today, and
# GitHub forbids approving your own PR — with required_approving_review_count=1
# and no bypass actor, the sole operator could not merge anything to `main`,
# bricking the merge=deploy pipeline. Strict status checks + require-up-to-date
# is the control that actually closes the alembic head race; the PR-review
# requirement is separate governance to be raised to >=1 once a second human
# reviewer exists. See the 2026-06-22 transfer note below.
#
# Rulesets/branch protection on a PRIVATE repo require a paid plan. History:
# the repo was on GitHub Free under a personal account (`alexanderantipov1`),
# where this API returned HTTP 403; the repo holds PHI and must stay private,
# so Layer 1 was deferred. RESOLVED 2026-06-22: the repo was transferred to the
# `FUSIONDENTALAI` organization (private, paid plan) and this ruleset was
# applied — it is now ACTIVE on `main`. This script stays as the idempotent
# source of truth; re-running it reconciles the live ruleset to this config.
#
# Idempotent: describe-or-create. Safe to re-run; updates the ruleset in
# place if it already exists. Prints only sanitized summaries.
#
# Usage:
#   gh auth login            # once, with repo admin scope
#   infra/scripts/setup_main_ruleset.sh
#
set -euo pipefail

RULESET_NAME="main protection (merge gate)"
# Exact GitHub check-run names (job-level checks) that must pass. These are
# the `name:` of the CI jobs in .github/workflows/ci.yml. The alembic
# single-head guard is a step inside "Lint + typecheck + tests", so that
# job-level context covers it.
CHECK_CI="Lint + typecheck + tests"
CHECK_WEB="Web — eslint + tsc + vitest"

repo_full="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
echo "Repo: ${repo_full}"

# Build the ruleset payload. strict_required_status_checks_policy=true is
# "require branch up to date before merging" — the exact-head / forced-rebase
# control that makes a concurrent migration head visible before merge.
payload="$(cat <<JSON
{
  "name": "${RULESET_NAME}",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] }
  },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true,
        "allowed_merge_methods": ["squash", "merge"]
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "do_not_enforce_on_create": false,
        "required_status_checks": [
          { "context": "${CHECK_CI}" },
          { "context": "${CHECK_WEB}" }
        ]
      }
    }
  ]
}
JSON
)"

# Find an existing ruleset with the same name (idempotency).
existing_id=""
if rulesets_json="$(gh api "repos/${repo_full}/rulesets" 2>/dev/null)"; then
  existing_id="$(printf '%s' "${rulesets_json}" \
    | python3 -c "import sys,json; rs=json.load(sys.stdin); print(next((str(r['id']) for r in rs if r.get('name')=='${RULESET_NAME}'),''))")"
else
  echo "ERROR: could not list rulesets for ${repo_full}." >&2
  echo "If this is HTTP 403 'Upgrade to GitHub Pro or make this repository public'," >&2
  echo "the repo is on a plan without rulesets. Upgrade to GitHub Team (the repo" >&2
  echo "must stay private — it holds PHI) and re-run. Until then, follow the" >&2
  echo "'Migration Merge Ordering' discipline in PARALLEL_WORK_POLICY.md." >&2
  exit 1
fi

if [ -n "${existing_id}" ]; then
  echo "Updating existing ruleset id=${existing_id}..."
  printf '%s' "${payload}" | gh api -X PUT "repos/${repo_full}/rulesets/${existing_id}" --input - >/dev/null
  echo "Updated '${RULESET_NAME}'."
else
  echo "Creating ruleset '${RULESET_NAME}'..."
  printf '%s' "${payload}" | gh api -X POST "repos/${repo_full}/rulesets" --input - >/dev/null
  echo "Created '${RULESET_NAME}'."
fi

echo "Done. Verify in GitHub → Settings → Rules → Rulesets, or:"
echo "  gh api repos/${repo_full}/rulesets --jq '.[] | \"\\(.name)\\t\\(.enforcement)\"'"

# Contract — ENG-223

## Snapshot payload additions

```json
{
  "mission": {
    "active_mission_name": "carestack-appointments-fetcher",
    "resolution_reason": "branch-match",
    "path": ".agents/orchestration/carestack-appointments-fetcher"
  }
}
```

Allowed `resolution_reason` values:

- `explicit-flag`     — operator passed `--mission <path>`.
- `branch-match`      — current git branch contains `ENG-\d+`, matched
                        against `runtime.json` Linear ids under
                        `.agents/orchestration/*/`.
- `mtime-fallback`    — no branch match; newest non-archived folder
                        used.
- `no-mission`        — no orchestration folders or no candidates.

`active_mission_name` is `null` only when `resolution_reason` is
`no-mission`.

## Detector resolution order

1. If `args.mission` is set → return that path, reason `explicit-flag`.
2. Read current git branch (`git rev-parse --abbrev-ref HEAD`). On
   failure or detached HEAD, skip to step 4.
3. Extract first `ENG-\d+` from branch name. For each folder under
   `.agents/orchestration/` (excluding `archived/` and dotfiles), open
   `runtime.json` if present and search:
   - `sessions[].linear_issue_id`
   - `handoffs[].linear_issue_id`
   First match wins; reason `branch-match`.
4. Fallback: newest folder mtime under `.agents/orchestration/`,
   excluding `archived/` and dotfiles; reason `mtime-fallback`.
5. If none found → return `None`, reason `no-mission`.

## Caching policy

No caching across requests for M1 of this fix. If profiling shows the
detector is too slow (>5 ms typical), add an in-process TTL cache in a
follow-up; for now we accept the cost in exchange for trivially
correct behavior.

## Backward compatibility

Existing snapshot consumers that ignore unknown fields keep working.
Existing `--mission <path>` callers see no behavior change.

# CLAUDE.md — CareStack docs

Local, agent-friendly reference for the CareStack Developer API.
Derived from `_source/carestack-v1.0.45.pdf` (PDF) and the extracted
text dump `_source/carestack-v1.0.45.txt`.

**Why this folder exists:** so an agent or developer doesn't need to
open the PDF to answer "how do I call endpoint X" or "what fields
does Patient have". Every public resource lives as a small, grep-able
markdown file next to its peers.

## How to use (agents)

- **Find a resource:** look at `README.md` — the full index — and
  jump into `resources/<name>.md`.
- **Need search or polling?** See `search/` (filtered one-shot)
  and `sync/` (modified-after polling).
- **Need billing / insurance?** See `insurance-manager/`.
- **Need the raw wording?** `_source/carestack-v1.0.45.txt` is the
  plain-text dump of the PDF — grep-friendly. Use it only when
  the summarised `.md` doesn't answer you.
- **Need the PDF itself?** `_source/carestack-v1.0.45.pdf`.

## Conventions inside the markdown

Each resource / endpoint doc follows the same template:

```
## <resource name>

**Fusion domain:** identity | ops | phi | billing | scheduling | ...
**PHI?:** yes | no | mixed  (what parts carry PHI)

### Object fields
| field | type | notes |

### Endpoints
- `METHOD /v1.0/<path>` — purpose
  - path params / query params / body
  - notable response fields
  - errors of interest

### Fusion mapping
- How this maps to our `packages/*` domains and tables.
- Ingestion strategy (sync / webhook / on-demand).
```

## Hard rules for editing these docs

- **English only** (see root `CLAUDE.md` language rule).
- **No long verbatim copies from the PDF.** Write short, factual
  summaries of endpoints / field shapes. Copyright is CareStack's.
- **PHI tagging is mandatory.** Every resource doc MUST state its
  PHI status so ops-only readers know what to leave out of
  dashboards and agent contexts.
- **When CareStack publishes a new version** (v1.0.46, ...):
  1. Replace `_source/*` files with the new version.
  2. Re-run the extraction for any changed sections.
  3. Bump the version header in `README.md`.
  4. Never edit a doc silently — note the delta in the PR.

## Current source version

`v1.0.45` (PDF dated Aug 04, 2025).

# Proposal — ENG-543: reversed-name compatibility + phone-strong / empty-lead auto-accept

**Status:** awaiting operator approval (contract_change, ENG-185). Propose-first;
no implementation until approved + Codex cross-runtime review scheduled.

## Root cause (read from `packages/identity/service.py`)

`_names_compatible` (line 289) builds token sets from **whole name fields**
(given / family / display) and checks set intersection:

- Lead hint: `given=""`, `family="Newton Patrick"`, `display="Newton Patrick"`
  → tokens `{"newton patrick"}`.
- Person: `given="Patrick"`, `family="Newton"`, `display="Patrick Newton"`
  → tokens `{"patrick", "newton", "patrick newton"}`.
- Intersection is **empty** → `name_compatible=false` → the `phone_name` rule
  (0.95, line 414) is skipped even though `phone_match=true` → falls through to
  `phone_only_ambiguous` (0.70) → **duplicate person + open candidate**.

So a single exact-phone case is lost purely on name *tokenization*, not on any
real disagreement. The order-invariance the function intends already exists at
field level; it just never splits "Newton Patrick" into words.

## Proposed change (scoped to `_names_compatible` + tier ladder)

### 1. Word-level, order-invariant name compatibility
Tokenize every name field into **words** (split on whitespace/punctuation,
lowercased, drop empties), union per side, then compare word sets. This handles:
- reversed First/Last (`Newton Patrick` ↔ `Patrick Newton`),
- everything-in-one-field (empty `given_name`, full name in `family`/`display`),
- middle names / suffixes (subset match below).

**Strength options (operator picks — this is the real safety decision):**

| Option | Rule | Patrick Newton | "John Smith" vs "Jane Smith" same phone | Verdict |
|---|---|---|---|---|
| A — any shared word | ≥1 common word token | ✅ merges | ⚠️ merges on shared "smith" | matches *today's* behavior (today already merges on a shared family field) |
| **B — subset match (recommended)** | all words of the shorter name appear in the longer | ✅ merges | ❌ stays separate ("jane" ∉ {john,smith}) | fixes the case, **reduces** family-phone false-merge risk vs today |
| C — exact word-set equality | identical word sets | ✅ merges | ❌ | safest, but misses middle-name/nickname variants |

Recommendation: **Option B**. It fixes the reported case and is *stricter* than
the current single-shared-token behavior, so it cannot regress safety.

### 2. Phone-strong auto-accept (unchanged tier, clarified)
With Option B, exact normalized E.164 phone match + name-compatible already fires
`phone_name` (0.95). No new tier needed; the fix is entirely in name comparison.
Keep the DOB/SSN hard veto (ENG-309) ahead of everything — different DOB/SSN
still never merges, regardless of phone.

### 3. Empty-lead rule
A lead with no email and only a name: `_names_compatible` already returns `True`
when one side has no usable tokens (absence ≠ conflict). Combined with a phone
match → `phone_name` auto-accept. With Option B this is covered; no separate
code path. (If the lead has *neither* name nor phone, it remains a new person —
correct.)

### 4. Multi-person phone stays ambiguous (no over-merge)
When >1 eligible candidate clears a tier-1 rule (`auto_accept_eligible > 1`,
line 436), the resolver already collapses to Tier 2 / open candidate. Preserve
this: a phone shared by several *distinct* names is NOT auto-merged — it surfaces
on the card (ENG-542) and waits for review.

## Files
- `packages/identity/service.py` — `_names_compatible` rewrite + a `_name_words`
  helper; no change to the tier ladder shape.
- `tests/identity/test_resolve_or_create_from_hint.py` — add: reversed name,
  single-field name, empty-lead+phone, family-phone-different-name stays open,
  DOB-veto still wins. Keep all existing cases green.

## Out of scope (handled elsewhere)
- Card surfacing of same-phone persons + persisting lead identifiers → ENG-542.
- Backfilling existing 6,287 open candidates + dedup-merge under the new rule →
  ENG-544 (depends on this).

## Risks
- Word-level matching is more permissive **only** vs Option C, not vs today.
  Option B is the recommended floor.
- `merge_event.reason` for backfilled merges = `duplicate_phone` /
  `cross_provider_match` (ENG-544).
- No PHI / DOB / SSN ever enters `MatchCandidate.evidence` — keep
  `_FORBIDDEN_EVIDENCE_KEYS` intact.

## Approval needed
1. Pick name-match strength: **A / B (recommended) / C**.
2. Confirm phone-strong does NOT override name disagreement (i.e. do NOT
   auto-merge different names on one phone — only surface on card). Default: yes.
3. On approval, Claude implements in the ENG-543 worktree; Codex cross-runtime
   review before integration; no merge to main without operator sign-off.

---

## APPROVED — 2026-06-20 (operator)

- **Name-match strength: Option B (subset match)** — all words of the shorter
  name must appear in the longer; order-invariant; handles reversed + single-field.
- **Different names on one phone: surface-only.** Do NOT auto-merge. Show both in
  the card same-phone block (ENG-542) + keep the open `MatchCandidate` for review.
  `auto_accept_eligible > 1` must stay Tier-2 / open.
- Implementation may proceed: Claude in the ENG-543 worktree → Codex cross-runtime
  review → NO merge to main without operator sign-off.

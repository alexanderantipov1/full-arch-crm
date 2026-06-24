"""Implant ``case_type`` taxonomy + resolver (ENG-539, B1.5).

``case_type`` is a derived, non-PHI analytics dimension on
``analytics.fact_patient_journey``: one coarse implant-case label per person,
derived from the ADA CDT codes of that person's implant procedures. Like every
other fact dimension it is a rebuildable projection (manual > auto >
unresolved); nothing here is a source of truth.

This module is the **in-house, operator-editable** taxonomy:

1. :data:`_CDT_CASE_SIGNAL` — the DRAFT CDT → coarse-signal map, bootstrapped
   from the real CareStack catalog observed in ENG-538. It is annotated
   ``# OPERATOR-CONFIRM`` because the operator owns the final say on which CDT
   maps to which case type; changing it is an operator decision, not a silent
   code edit.
2. :func:`resolve_case_type` — the per-person resolver: given the multiset of a
   person's implant-procedure CDT codes, it applies a DOCUMENTED precedence and
   returns exactly one :data:`CaseType` (or ``None`` = *unclassified*, which the
   builder ships as a NULL ``case_type`` + a needs-review signal). It NEVER
   guesses: an ambiguous / non-determinative implant footprint stays
   unclassified.

Why CDT-only, and what is deliberately out of auto scope:

* The CDT standard says *"implant, abutment-supported fixed denture, edentulous
  arch"* (full-arch) but NOT whether it is **All-on-4** vs **All-on-6**, and has
  no code for **zygomatic** implants or for the **arch side**
  (upper / lower / dual). Those finer labels (``all_on_4`` / ``all_on_6`` /
  ``zygomatic`` / ``full_arch_upper`` / ``full_arch_lower`` / ``dual_arch``) are
  therefore **manual-only / future** — set via ENG-513 enrichment and the review
  surface, never auto-derived. See :data:`MANUAL_ONLY_CASE_TYPES`.
* Single-vs-multiple is counted on the **surgical-placement** codes — operator
  decision 2026-06-20: D6010 plus the placement variants D6012 / D6013 / D6040 /
  D6050 (interim / mini / eposteal / transosteal), aligned with the ENG-511
  implant-surgery set so a patient with a surgery is never "surgery yes, case
  type unclassified". Second-stage/uncovery (D6011 / D6011NC) is NOT a new
  placement and stays non-determinative.

The catalog read (``procedureCodeId`` → CDT) happens via
``CatalogService.resolve_procedure_codes`` in the caller (the fact builder); this
module is pure (CDT strings in, label out) so it is trivially unit-testable and
holds no DB or cross-domain dependency.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

# Auto-derivable coarse case types (the only values the resolver may emit).
CaseType = Literal[
    "single_implant",
    "multiple_implants",
    "all_on_x",
    "overdenture",
    "implant_bridge",
]

# Finer labels that CDT CANNOT distinguish — operator/manual enrichment only,
# NEVER auto-derived (documented for completeness; the column accepts them when
# an operator sets them through the ENG-513 path).
MANUAL_ONLY_CASE_TYPES: frozenset[str] = frozenset(
    {
        "all_on_4",  # CDT only says "All on X" — count is not in the code
        "all_on_6",
        "zygomatic",  # no standard CDT for zygomatic implants
        "full_arch_upper",  # arch side is not in the CDT
        "full_arch_lower",
        "dual_arch",
    }
)

# Every value the ``case_type`` column may legitimately hold (auto OR manual).
ALL_CASE_TYPES: frozenset[str] = frozenset(
    {
        "single_implant",
        "multiple_implants",
        "all_on_x",
        "overdenture",
        "implant_bridge",
    }
) | MANUAL_ONLY_CASE_TYPES

# Coarse per-CDT signal. NOT the final case_type — the resolver combines a
# person's signals (with the D6010 placement count) into one case_type.
_Signal = Literal[
    "placement",  # D6010 surgical placement — COUNTED for single vs multiple
    "all_on_x",  # full-arch fixed denture / "All on X"
    "overdenture",  # implant/abutment-supported REMOVABLE denture
    "implant_bridge",  # implant-supported FPD retainer/crown
    "implant_other",  # implant-category but non-determinative (see module doc)
]

# DRAFT CDT → signal map (ENG-539). OPERATOR-CONFIRM: bootstrapped from the real
# CareStack implant-category (cdtCategoryId=8) codes observed in ENG-538. The
# operator owns the final mapping; every entry below is provisional until
# confirmed. Matching is EXACT on ``code.strip().upper()`` (the catalog stores
# codes stripped), so custom variants like ``D6010.A`` / ``D6011NC`` must be
# spelled exactly.
_CDT_CASE_SIGNAL: dict[str, _Signal] = {
    # --- surgical placement (counted for single vs multiple) ---
    # OPERATOR-CONFIRMED 2026-06-20: all surgical-placement variants count as a
    # placement, aligned with the ENG-511 implant-surgery set (not D6010 only).
    "D6010": "placement",  # endosteal implant body
    "D6012": "placement",  # interim implant body for transitional prosthesis
    "D6013": "placement",  # mini implant
    "D6040": "placement",  # eposteal implant
    "D6050": "placement",  # transosteal implant
    # --- full-arch / "All on X" ---
    "D6010.A": "all_on_x",  # custom "Implant All on X" (catalog id 228501)
    "D6114": "all_on_x",  # implant/abutment-supported fixed denture, max (edentulous arch)
    "D6115": "all_on_x",  # implant/abutment-supported fixed denture, mand (edentulous arch)
    "D6118": "all_on_x",  # implant/abutment-supported interim fixed denture (edentulous arch)
    # --- overdenture (removable) ---
    "D6053": "overdenture",  # implant-supported removable denture
    "D6054": "overdenture",  # abutment-supported removable denture
    # --- implant-supported bridge (FPD retainers / crowns) ---
    "D6065": "implant_bridge",  # implant-supported porcelain/ceramic crown
    "D6066": "implant_bridge",  # implant-supported porcelain-fused-to-metal crown
    "D6068": "implant_bridge",  # abutment-supported retainer crown for FPD
    "D6075": "implant_bridge",  # implant-supported retainer for ceramic FPD
    # --- implant-category but NON-determinative (review-only, never classifies) ---
    "D6011": "implant_other",  # second-stage implant body (uncovery — not a new placement)
    "D6011NC": "implant_other",  # custom uncovery / second-stage variant (id 107024)
    "D6056": "implant_other",  # prefabricated abutment
    "D6057": "implant_other",  # custom abutment
    "D6058": "implant_other",  # abutment-supported porcelain/ceramic crown
    "D6080": "implant_other",  # implant maintenance procedure
    "D6100": "implant_other",  # surgical removal of implant body
    "D6103": "implant_other",  # bone graft for implant defect
    "D6104": "implant_other",  # bone graft at time of implant placement
}


@dataclass(frozen=True)
class CaseTypeResolution:
    """Outcome of resolving one person's implant-procedure CDT set.

    * ``case_type`` — the auto-derived label, or ``None`` when the implant
      footprint is non-determinative (*unclassified* — shipped as NULL +
      ``method='unresolved'`` and surfaced for manual review).
    * ``has_implant`` — ``True`` when the person has ANY implant-category CDT
      (even a non-determinative one). Drives the review surface: a person with
      ``has_implant and case_type is None`` is "has implant procedures but
      unclassified", the exact cohort an operator should triage.
    """

    case_type: CaseType | None
    has_implant: bool


def classify_cdt(code: str) -> _Signal | None:
    """Map ONE CDT code to its coarse implant signal (``None`` if not implant)."""
    return _CDT_CASE_SIGNAL.get(code.strip().upper())


def resolve_case_type(cdt_codes: Iterable[str]) -> CaseTypeResolution:
    """Resolve one person's implant-procedure CDT set to a single ``case_type``.

    ``cdt_codes`` is the multiset of CDT codes across the person's DISTINCT
    implant procedures (one entry per procedure, so the D6010 count is the
    number of placement procedures). The DOCUMENTED precedence is::

        all_on_x  >  overdenture  >  implant_bridge  >  multiple_implants  >  single_implant

    Rationale: a full-arch / removable / bridge prosthetic signal is a stronger,
    more specific statement of the case than a bare placement count, so it wins
    even when D6010 placements are also present (a full-arch case legitimately
    carries several placements). Among placement-only footprints, ``>= 2`` D6010
    placements → ``multiple_implants``, exactly one → ``single_implant``.

    No determinative signal (only non-determinative implant codes, e.g. a lone
    abutment or a mini-implant) → ``case_type=None`` with ``has_implant=True``
    (*unclassified*, needs review). No implant code at all → ``case_type=None``
    with ``has_implant=False`` (not an implant patient; not flagged). NEVER
    guesses.
    """
    placement_count = 0
    has_all_on_x = False
    has_overdenture = False
    has_bridge = False
    has_any_implant = False

    for code in cdt_codes:
        signal = classify_cdt(code)
        if signal is None:
            continue
        has_any_implant = True
        if signal == "placement":
            placement_count += 1
        elif signal == "all_on_x":
            has_all_on_x = True
        elif signal == "overdenture":
            has_overdenture = True
        elif signal == "implant_bridge":
            has_bridge = True
        # "implant_other" only flips has_any_implant (review eligibility).

    case_type: CaseType | None
    if has_all_on_x:
        case_type = "all_on_x"
    elif has_overdenture:
        case_type = "overdenture"
    elif has_bridge:
        case_type = "implant_bridge"
    elif placement_count >= 2:
        case_type = "multiple_implants"
    elif placement_count == 1:
        case_type = "single_implant"
    else:
        case_type = None

    return CaseTypeResolution(case_type=case_type, has_implant=has_any_implant)

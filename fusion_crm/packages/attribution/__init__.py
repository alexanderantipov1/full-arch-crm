"""Lead source attribution (ENG-446).

Derived semantic layer that models a lead's origin as a hierarchical
distribution chain (vendor → channel → campaign → ad_set → ad → form) and a
resolved per-lead attribution, re-buildable from raw evidence. Block A
(ENG-447) ships the schema + controlled vocabulary; the waterfall resolver
(ENG-448) and manual enrichment (ENG-449) build on it.

See ``.agents/strategy/LEAD_SOURCE_ATTRIBUTION_DESIGN.md``.
"""

"""Catalog domain package (ENG-420).

Workspace-wide reference data sourced from external systems. The first
member is the CareStack procedure-code catalog
(``catalog.procedure_code``) — a CDT/CPT lookup table that lets every
domain join an integer ``procedureCodeId`` against its CDT code string +
description without re-pulling the CareStack catalog inline.

Do not re-export models or services from this module.
"""

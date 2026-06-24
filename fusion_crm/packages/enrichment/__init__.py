"""Enrichment domain package (ENG-439, Block F).

A small, clean domain for *our own* fields layered over the canonical
entities (`identity.person`, `ops.lead`, opportunities, …). Annotations are
free-form key/value rows our staff add from the UI today and that the chat
action path (Block G) will write later — both through ONE service
(:class:`packages.enrichment.service.EnrichmentService`).

Completeness of external data lives at the RAW ingest layer (invariant #11);
this domain is the opposite end: deliberately small, curated, human-authored
context that has no home in any provider-sourced schema.

Do not re-export models or services from this module.
"""

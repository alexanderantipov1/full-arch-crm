"""Interaction domain — slim Phase 1 subset.

Owns ``interaction.event``: append-only timeline of semantic events that
happen to a Person (Lead created, Consultation rescheduled, etc).

Phase 1 ships only ``event``. The full v0.2 package (event_content,
transcript_artifact, message_artifact) lands in Phase 3 (M3 — Interaction
ingestion).

The PUBLIC surface is :class:`packages.interaction.service.InteractionService`.
Models and the repository are implementation detail; do not import them
from outside this package.
"""

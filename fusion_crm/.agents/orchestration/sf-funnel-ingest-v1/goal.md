# Goal — sf-funnel-ingest-v1

Make raw ingest change-driven and complete the Salesforce funnel capture so
the agent layer can read a person's full story (lead → conversion →
opportunity → pipeline movement) without tick-duplicate noise.

## Business goal

The owner's doctrine: every funnel segment is an event and person context.
Raw rows must be written only when something changed at the provider; every
SF funnel object (Lead conversion fields, attribution, Contact, Account,
Opportunity, OpportunityHistory) must land as person-linked evidence.

## Linear

- ENG-381 — Idempotent ingest: watermark + change-guard across SF/CareStack
  pullers, dedupe cleanup (executes first).
- ENG-382 — SF funnel provenance: conversion fields, UTM attribution,
  opportunity person link, stage history (blocked-by ENG-381: new pullers
  must be born watermark-first).

## Why now

Measured on 2026-06-09: ingest.raw_event holds ~2.9M rows where ~260k
distinct objects exist (e.g. 406,592 rows for 539 opportunities). Every
~90s tick re-pulls fixed windows and captures unconditionally. Meanwhile
opportunities carry the real UTM attribution and are linked to zero persons.

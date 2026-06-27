"""Outreach domain — operator-account email outreach (ADR-0004).

Owns templates, campaigns, sends, suppression list, and the outbound
queue table. The send pipeline (worker + provider clients) ships under
ENG-132; this package is the data + service surface that pipeline
binds against.
"""

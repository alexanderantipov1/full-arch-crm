"""Structured JSON logging.

In production we ship JSON logs to stdout so the orchestrator (Docker / future
log forwarder) can ingest them. In development we keep human-readable output.
"""

from __future__ import annotations

import logging
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import structlog

from .config import get_settings

# Query-string keys whose values are secrets and must never reach a log sink.
# Lower-cased; matched case-insensitively. Covers OAuth/access tokens and the
# client-secret/refresh/code params that the integration HTTP clients send to
# Google / Meta token + Graph endpoints.
_SECRET_QUERY_KEYS = frozenset(
    {
        "access_token",
        "token",
        "refresh_token",
        "id_token",
        "fb_exchange_token",
        "client_secret",
        "developer_token",
        "key",
        "api_key",
        "code",
        "password",
        "secret",
        "assertion",
    }
)
_REDACTED = "***"


def redact_url(url: str) -> str:
    """Return ``url`` with secret-bearing query-param values masked as ``***``.

    Use this before putting any provider URL into a log/error field. The
    integration clients pass OAuth/access tokens in the query string (Meta
    Graph ``?access_token=...``; the ``paging.next`` cursor URL carries the
    token baked in), so a raw URL in a log line is a durable secret leak.
    Non-secret params and the path are preserved so the line stays useful.
    Falls back to a scheme+host+path-only string if the URL cannot be parsed.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if not parts.query:
        return url
    redacted_pairs = [
        (k, _REDACTED if k.lower() in _SECRET_QUERY_KEYS else v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
    ]
    new_query = urlencode(redacted_pairs)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment)
    )


def configure_logging() -> None:
    """Idempotent logging setup. Safe to call multiple times."""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    # Clamp HTTP-client request loggers so the per-request URL never reaches a
    # sink. httpx emits an INFO-level ``HTTP Request: <method> <url> ...`` line
    # whose URL can carry an OAuth/access token in the query string (e.g. Meta
    # Graph ``?access_token=...`` and the Google OAuth token-refresh URL). Logs
    # hit disk + backups and outlive the dev phase, so a logged token is a
    # durable secret leak (root CLAUDE.md → Logging: secrets must never be
    # logged). WARNING+ still surfaces real HTTP/connection errors; only the
    # INFO request line is silenced. Parent names cover httpcore's children
    # (``httpcore.connection`` / ``.http11`` / ...).
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_production:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)

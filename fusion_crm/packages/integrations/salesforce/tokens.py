"""Phase 1 token storage adapter for Salesforce.

Reads/writes tokens from ``apps/web/.sf-tokens.json`` — the same dev file the
Next.js OAuth flow maintains. When production token storage lands (FUS-22 —
encrypted column on ``integrations.integration_account``), swap this module
for a DB-backed reader; the rest of the package consumes the ``SfTokens``
dataclass and is unchanged.

Path resolution:
  1. ``SF_DEV_TOKEN_FILE`` env var if set (absolute or repo-relative)
  2. else ``<repo_root>/apps/web/.sf-tokens.json``
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from packages.core.config import get_settings

from .exceptions import SfNotConnectedError


@dataclass(frozen=True)
class SfTokens:
    """Salesforce OAuth tokens. Frozen — refresh produces a new instance."""

    access_token: str
    instance_url: str
    refresh_token: str | None = None
    issued_at: str | None = None
    saved_at: str | None = None


def default_token_file_path() -> Path:
    """Resolve ``apps/web/.sf-tokens.json`` from repo root, honoring the env override."""
    setting = get_settings().sf_dev_token_file
    if setting:
        configured = Path(setting)
        if configured.is_absolute():
            return configured
        # Relative paths are resolved against repo root for stability across CWDs.
        return _repo_root() / configured
    return _repo_root() / "apps" / "web" / ".sf-tokens.json"


def read_dev_tokens(path: Path | None = None) -> SfTokens:
    """Read tokens from the dev JSON file.

    Raises ``SfNotConnectedError`` when the file is missing, malformed, or
    missing required fields. The error carries the path so the caller can log
    a clear hint.
    """
    target = path or default_token_file_path()
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SfNotConnectedError(
            "salesforce tokens file not found",
            details={"path": str(target)},
        ) from exc
    except OSError as exc:
        raise SfNotConnectedError(
            "salesforce tokens file unreadable",
            details={"path": str(target)},
        ) from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SfNotConnectedError(
            "salesforce tokens file is malformed",
            details={"path": str(target)},
        ) from exc

    if not isinstance(data, dict) or not data.get("access_token") or not data.get("instance_url"):
        raise SfNotConnectedError(
            "salesforce tokens file missing required fields (access_token, instance_url)",
            details={"path": str(target)},
        )

    return SfTokens(
        access_token=data["access_token"],
        instance_url=data["instance_url"],
        refresh_token=data.get("refresh_token"),
        issued_at=data.get("issued_at"),
        saved_at=data.get("saved_at"),
    )


def persist_dev_tokens(tokens: SfTokens, path: Path | None = None) -> None:
    """Write tokens back to the dev file (used after a successful refresh).

    Refreshes ``saved_at`` to the current UTC ISO timestamp. Preserves
    ``refresh_token`` and ``issued_at`` when present.
    """
    target = path or default_token_file_path()
    payload: dict[str, str] = {
        "access_token": tokens.access_token,
        "instance_url": tokens.instance_url,
        "saved_at": datetime.now(UTC).isoformat(),
    }
    if tokens.refresh_token:
        payload["refresh_token"] = tokens.refresh_token
    if tokens.issued_at:
        payload["issued_at"] = tokens.issued_at
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _repo_root() -> Path:
    # packages/integrations/salesforce/tokens.py → parents[3] = repo root
    return Path(__file__).resolve().parents[3]

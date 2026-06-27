#!/usr/bin/env python3
"""Wire tenant locations to their Mattermost team (ENG-458).

Reads the workspace manifest (`infra/docker/mattermost/workspace.yaml`) and, for
every team's ``carestack_location_ids``, sets
``tenant.location.external_ref["mattermost_team"] = <team name>`` on the matching
location. The notification engine then maps a consultation's ``location_id`` to
that team so cards route to the clinic's own ``#scheduls`` / ``#consult-reminders``.

The team↔location link is OPERATOR DATA (not derivable from names) — fill the
``carestack_location_ids`` lists in the manifest first. Idempotent: re-running
only overwrites the ``mattermost_team`` key.

Usage (against the env the DATABASE_URL points at — local by default; the
operator runs it against prod explicitly):

    python infra/scripts/map_location_teams.py [--tenant-slug fusion-dental-implants] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import yaml

from packages.core.config import get_settings
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.tenant.service import LocationService, TenantService

DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "docker" / "mattermost" / "workspace.yaml"


def _principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
        context={"source": "infra.map_location_teams"},
    )


async def _run(manifest_path: Path, tenant_slug: str, *, dry_run: bool) -> int:
    manifest = yaml.safe_load(manifest_path.read_text())
    pairs: list[tuple[int, str]] = []
    for team in manifest.get("teams", []):
        for cs_id in team.get("carestack_location_ids") or []:
            pairs.append((int(cs_id), team["name"]))

    if not pairs:
        print(
            "No carestack_location_ids in the manifest yet — fill them in "
            f"{manifest_path} before wiring location→team."
        )
        return 1

    changed = 0
    async with async_session() as session:
        tenant = await TenantService(session).get_by_slug(tenant_slug)
        tenant_id = TenantId(tenant.id)
        locations = LocationService(session)
        for cs_id, team_name in pairs:
            location = await locations.find_by_carestack_id(tenant_id, cs_id)
            if location is None:
                print(f"  carestack_location_id={cs_id} → team {team_name!r}: NO LOCATION (skipped)")
                continue
            current = (location.external_ref or {}).get("mattermost_team")
            if current == team_name:
                print(f"  {location.name!r} (cs={cs_id}) → {team_name!r}: already set")
                continue
            print(
                f"  {location.name!r} (cs={cs_id}) → mattermost_team={team_name!r}"
                + (" [DRY-RUN]" if dry_run else "")
            )
            if not dry_run:
                # Read-modify-write the JSONB; reassign so SQLAlchemy tracks it.
                ext = dict(location.external_ref or {})
                ext["mattermost_team"] = team_name
                location.external_ref = ext
                changed += 1
        if not dry_run and changed:
            await session.commit()

    print(f"\n{'would update' if dry_run else 'updated'} {changed} location(s)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Map tenant locations to Mattermost teams.")
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument(
        "--tenant-slug",
        default=get_settings().tenant_default_slug,
        help="tenant whose locations to wire (default: TENANT_DEFAULT_SLUG)",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    return asyncio.run(
        _run(args.manifest, args.tenant_slug, dry_run=args.dry_run)
    )


if __name__ == "__main__":
    raise SystemExit(main())

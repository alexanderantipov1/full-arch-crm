#!/usr/bin/env python3
"""Map a CareStack provider (doctor) to a Mattermost username (ENG-543).

Interim operator tool until the Messenger settings UI (Step 2b) lands. Attaches
a ``mattermost_username`` identifier to the doctor's ``actor.actor`` (resolved by
its ``carestack_provider_id``), so the T-15m consult-reminder can @mention the
doctor. Idempotent (``attach_identifier`` is idempotent on ``(kind, value)``).

CLI::

    # list provider actors + any existing mattermost_username
    python3 infra/scripts/set_provider_mattermost.py --list

    # map one provider
    python3 infra/scripts/set_provider_mattermost.py \\
        --carestack-provider-id 1 --mattermost-username drantipov

``--tenant-id`` is optional (defaults to Settings.tenant_default_slug).
The doctor's Mattermost user must also be a MEMBER of the team's
#consult-reminders channel to actually receive the ping.
"""
from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from packages.core.config import get_settings
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.tenant.service import TenantService

_PROVIDER_KIND = "carestack_provider_id"
_MM_KIND = "mattermost_username"


async def _run(args: argparse.Namespace) -> int:
    from packages.actor.service import ActorService

    async with async_session() as session:
        if args.tenant_id:
            tenant_id = TenantId(UUID(args.tenant_id))
        else:
            tenant = await TenantService(session).get_by_slug(
                get_settings().tenant_default_slug
            )
            tenant_id = TenantId(tenant.id)

        actors = ActorService(session)

        if args.list:
            # Show every provider actor + its current mattermost_username (if any).
            print(f"Provider actors for tenant {tenant_id}:")
            # find_by_identifier is per-value; instead list via the directory.
            from sqlalchemy import select

            from packages.actor.models import Actor, ActorIdentifier

            stmt = (
                select(Actor, ActorIdentifier.value)
                .join(ActorIdentifier, ActorIdentifier.actor_id == Actor.id)
                .where(Actor.tenant_id == tenant_id)
                .where(ActorIdentifier.kind == _PROVIDER_KIND)
                .order_by(Actor.name)
            )
            for actor, cs_id in (await session.execute(stmt)).all():
                mm = await actors.resolve_linked_identifier(
                    tenant_id, _PROVIDER_KIND, cs_id, _MM_KIND
                )
                print(f"  cs={cs_id:>6}  {actor.name!r:34} mattermost={mm or '—'}")
            return 0

        if not args.carestack_provider_id or not args.mattermost_username:
            print("ERROR: pass --carestack-provider-id and --mattermost-username (or --list)")
            return 2

        actor = await actors.find_by_identifier(
            tenant_id, _PROVIDER_KIND, args.carestack_provider_id
        )
        if actor is None:
            print(f"No provider actor for carestack_provider_id={args.carestack_provider_id}")
            return 1

        username = args.mattermost_username.lstrip("@")
        await actors.attach_identifier(tenant_id, actor.id, _MM_KIND, username)
        await session.commit()
        print(f"Mapped {actor.name!r} (cs={args.carestack_provider_id}) -> @{username}")
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Map a CareStack provider to a Mattermost username.")
    ap.add_argument("--tenant-id", default=None)
    ap.add_argument("--carestack-provider-id", default=None)
    ap.add_argument("--mattermost-username", default=None)
    ap.add_argument("--list", action="store_true", help="list provider actors + mappings")
    return asyncio.run(_run(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())

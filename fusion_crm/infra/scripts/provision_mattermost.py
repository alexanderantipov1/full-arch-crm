#!/usr/bin/env python3
"""Idempotent Mattermost workspace provisioner (ENG-458).

Reads a declarative manifest (`infra/docker/mattermost/workspace.yaml`) and
ensures the target Mattermost instance has the same teams + channels, with the
notifier bot a member of each. Safe to re-run: existing teams/channels/
memberships are detected and left untouched.

The manifest is the single source of truth so local dev and prod are
reproducible from the same file. Channel IDs are environment-specific; this
script DISCOVERS them at runtime and prints the (team, channel) -> id map.
Nothing is hardcoded.

Usage:
    MM_BASE_URL=http://127.0.0.1:8065 MM_ADMIN_TOKEN=... \
        python infra/scripts/provision_mattermost.py [--dry-run] [--json out.json]

The admin token must belong to a System Admin (team/channel creation requires
it). Read it from the env — never pass secrets on the command line in shells
that log history.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx
import yaml

DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "docker" / "mattermost" / "workspace.yaml"


class Provisioner:
    def __init__(self, base_url: str, token: str, *, dry_run: bool) -> None:
        self.base_url = base_url.rstrip("/")
        self.dry_run = dry_run
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )

    # --- low-level helpers -------------------------------------------------
    def _get(self, path: str) -> httpx.Response:
        return self.client.get(path)

    def _post(self, path: str, body: dict) -> httpx.Response:
        return self.client.post(path, json=body)

    # --- teams -------------------------------------------------------------
    def ensure_team(self, name: str, display_name: str) -> str:
        r = self._get(f"/api/v4/teams/name/{name}")
        if r.status_code == 200:
            tid = r.json()["id"]
            print(f"  team {name!r}: exists (id={tid})")
            return tid
        if self.dry_run:
            print(f"  team {name!r}: WOULD CREATE")
            return "<dry-run>"
        r = self._post("/api/v4/teams", {"name": name, "display_name": display_name, "type": "O"})
        r.raise_for_status()
        tid = r.json()["id"]
        print(f"  team {name!r}: CREATED (id={tid})")
        return tid

    # --- channels ----------------------------------------------------------
    def ensure_channel(self, team_id: str, team_name: str, name: str, display_name: str) -> str:
        r = self._get(f"/api/v4/teams/{team_id}/channels/name/{name}")
        if r.status_code == 200:
            cid = r.json()["id"]
            print(f"    channel {team_name}/{name}: exists (id={cid})")
            return cid
        if self.dry_run:
            print(f"    channel {team_name}/{name}: WOULD CREATE")
            return "<dry-run>"
        r = self._post(
            "/api/v4/channels",
            {"team_id": team_id, "name": name, "display_name": display_name, "type": "O"},
        )
        r.raise_for_status()
        cid = r.json()["id"]
        print(f"    channel {team_name}/{name}: CREATED (id={cid})")
        return cid

    # --- bot membership ----------------------------------------------------
    def bot_user_id(self, username: str) -> str | None:
        r = self._get(f"/api/v4/users/username/{username}")
        if r.status_code == 200:
            return r.json()["id"]
        print(f"  bot {username!r}: NOT FOUND on this instance (skipping membership)")
        return None

    @staticmethod
    def _is_already_member(r: httpx.Response) -> bool:
        """True when a member-add failed only because the user is already in.

        Mattermost returns 200/201 on add (incl. re-add) on most versions, but
        some return 400 with an ``...exists...`` app-error id. Treat that as
        success so a re-run stays idempotent and quiet.
        """
        if r.status_code in (200, 201):
            return True
        if r.status_code == 400 and "exist" in r.text.lower():
            return True
        return False

    def ensure_team_member(self, team_id: str, user_id: str) -> None:
        if self.dry_run:
            return
        r = self._post(f"/api/v4/teams/{team_id}/members", {"team_id": team_id, "user_id": user_id})
        if not self._is_already_member(r):
            print(f"    [warn] add bot to team failed: {r.status_code} {r.text[:160]}")

    def ensure_channel_member(self, channel_id: str, user_id: str) -> None:
        if self.dry_run:
            return
        r = self._post(f"/api/v4/channels/{channel_id}/members", {"user_id": user_id})
        if not self._is_already_member(r):
            print(f"      [warn] add bot to channel failed: {r.status_code} {r.text[:160]}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Provision Mattermost teams/channels from a manifest.")
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--base-url", default=os.environ.get("MM_BASE_URL"))
    ap.add_argument("--token", default=os.environ.get("MM_ADMIN_TOKEN"))
    ap.add_argument(
        "--bot-username",
        default=os.environ.get("MM_BOT_USERNAME"),
        help=(
            "notifier bot username to add to every team/channel; overrides the "
            "manifest's bot.username (the bot account is env-specific: prod "
            "'fusion-crm', local 'fusion')"
        ),
    )
    ap.add_argument("--dry-run", action="store_true", help="report actions without mutating")
    ap.add_argument("--json", type=Path, help="write the resolved (team,channel)->id map here")
    args = ap.parse_args()

    if not args.base_url or not args.token:
        print("ERROR: set --base-url/MM_BASE_URL and --token/MM_ADMIN_TOKEN", file=sys.stderr)
        return 2

    manifest = yaml.safe_load(args.manifest.read_text())
    bot_username = args.bot_username or (manifest.get("bot") or {}).get("username")

    prov = Provisioner(args.base_url, args.token, dry_run=args.dry_run)
    print(f"Target: {prov.base_url}  (dry_run={args.dry_run})")

    bot_id = prov.bot_user_id(bot_username) if bot_username else None

    resolved: dict[str, dict[str, str]] = {}
    for team in manifest["teams"]:
        tname, tdisp = team["name"], team["display_name"]
        print(f"\nTEAM {tname}")
        tid = prov.ensure_team(tname, tdisp)
        if bot_id and not args.dry_run:
            prov.ensure_team_member(tid, bot_id)
        resolved[tname] = {}
        for ch in team["channels"]:
            cid = prov.ensure_channel(tid, tname, ch["name"], ch["display_name"])
            resolved[tname][ch["name"]] = cid
            if bot_id and not args.dry_run and cid != "<dry-run>":
                prov.ensure_channel_member(cid, bot_id)

    print("\n=== resolved (team, channel) -> channel_id ===")
    print(json.dumps(resolved, indent=2, ensure_ascii=False))
    if args.json:
        args.json.write_text(json.dumps(resolved, indent=2, ensure_ascii=False))
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

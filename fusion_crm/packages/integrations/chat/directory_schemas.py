"""DTOs for the staff Messenger directory (ENG-564).

Output models the staff "Messenger" settings tab renders: a read-only mirror
of the Mattermost server's teams and, per team, its channels. The data comes
from the Mattermost REST API as plain dicts (not ORM rows), so these are plain
Pydantic models with no ``from_attributes`` — the service builds them from the
mapped API payload.

Field names mirror the Zod schemas in
``apps/web/lib/api/schemas/messenger.ts`` exactly.
"""

from __future__ import annotations

from pydantic import BaseModel


class MessengerTeamOut(BaseModel):
    """One Mattermost team (workspace) in the directory listing.

    ``url`` is the team's landing page on the Mattermost server, built by the
    adapter from the team ``name`` (slug); the staff card renders it as an
    external link.
    """

    id: str
    name: str
    display_name: str
    url: str


class MessengerChannelOut(BaseModel):
    """One channel within a team.

    ``type`` is the raw Mattermost channel type (``"O"`` open / public,
    ``"P"`` private); the staff card maps it to a human label.
    """

    id: str
    name: str
    display_name: str
    type: str
    purpose: str


__all__ = ["MessengerTeamOut", "MessengerChannelOut"]

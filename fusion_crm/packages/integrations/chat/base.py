"""Chat provider interface (ENG-436, Block C).

Defines the minimal contract the notification dispatcher
(``apps.worker.jobs.notification_dispatch``) depends on to post a
rendered message to a corporate chat workspace. The concrete
Mattermost adapter lands in Block B (ENG-435); this module only
declares the shapes so Block C is provable end-to-end with a mocked
provider.

The interface is deliberately tiny: one ``post`` coroutine taking a
``ChatMessage`` and returning a ``ChatPostResult``. Providers translate
their own HTTP / SDK errors into ``ChatPostResult(ok=False, error=...)``
or raise — the dispatcher treats both as a failed row.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One message to post to a chat channel.

    ``channel`` is the provider's channel id / name; ``text`` is the
    plain-text body; ``blocks`` is an optional list of provider-specific
    rich blocks (Mattermost attachments / Slack blocks); ``extra``
    carries any provider hints (e.g. a thread root id) without widening
    the interface.
    """

    channel: str
    text: str
    blocks: list[object] | None = None
    extra: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChatPostResult:
    """Outcome of a single ``ChatProvider.post`` call."""

    ok: bool
    provider_message_id: str | None = None
    error: str | None = None


@runtime_checkable
class ChatProvider(Protocol):
    """A corporate-chat provider capable of posting a message."""

    async def post(self, message: ChatMessage) -> ChatPostResult: ...

    async def resolve_channel_id(self, channel: str) -> str | None:
        """Resolve a channel NAME to the provider's channel id.

        If ``channel`` already looks like an id, return it unchanged.
        Returns ``None`` when the name cannot be resolved (never raises),
        mirroring the adapter's no-raise error contract.
        """
        ...


__all__ = ["ChatMessage", "ChatPostResult", "ChatProvider"]

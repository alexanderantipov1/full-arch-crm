"""Tools layer — the ONLY surface AI agents are allowed to call.

Tools are thin, JSON-friendly wrappers around services. They:
  * receive a ``Principal`` (so authorisation/audit work end-to-end)
  * receive an ``AsyncSession`` (so they participate in the caller's UoW)
  * NEVER touch repositories or the DB directly
  * MUST be registered in ``packages.tools.registry`` to be callable

Adding a new tool: add a function decorated with ``@tool``, then export it from
``registry.ALL_TOOLS``.
"""

from .registry import ALL_TOOLS, get_tool  # noqa: F401

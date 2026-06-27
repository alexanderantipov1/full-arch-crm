"""Windows-style timezone string → IANA name mapping.

CareStack returns ``timeZone`` values in Microsoft's Windows format
(e.g. ``"Pacific Standard Time"``). Postgres / Python expect IANA
names (``"America/Los_Angeles"``). This module is a small lookup
table covering the zones we currently onboard tenants in.

Source for the canonical mapping is the Unicode CLDR
``windowsZones.xml`` file. We only enumerate the values we have seen
or expect to see — extend as we onboard tenants in other zones.
"""

from __future__ import annotations

# Windows display name → IANA zone name. Keys are case-sensitive and
# must match the exact string CareStack returns; CareStack uses the
# Microsoft display form ("Pacific Standard Time"), not abbreviations
# ("PST").
WINDOWS_TO_IANA: dict[str, str] = {
    # US continental — these are the four CareStack actually returns today.
    "Pacific Standard Time": "America/Los_Angeles",
    "Mountain Standard Time": "America/Denver",
    "Central Standard Time": "America/Chicago",
    "Eastern Standard Time": "America/New_York",
    # UTC fallback. CareStack does not normally use this, but the spec
    # allows it and we'd rather store a usable IANA name than the
    # Windows label.
    "UTC": "UTC",
}


def to_iana(windows_tz: str | None) -> str | None:
    """Map a Windows zone string to its IANA equivalent.

    Returns ``None`` when the input is ``None`` or empty so callers
    can pass the raw CareStack value through. Returns the original
    string when the mapping is unknown — the caller logs a warning
    and keeps the row's existing ``timezone_override`` rather than
    overwriting it with garbage.
    """
    if not windows_tz:
        return None
    return WINDOWS_TO_IANA.get(windows_tz, windows_tz)

"""Drift-prevention test for `infra/env/production.env.reference`.

Implements `docs/DEPLOYMENT_RULES.md` §1 ("If a variable is added to
`Settings` but is missing from the deploy/env reference path, CI
should fail"). The test introspects `packages.core.config.Settings`,
parses the reference file, and asserts two invariants:

1. Every env name documented in the reference resolves to a real
   `Settings` field (catches obsolete/typo names like
   `INTEGRATIONS_ENCRYPTION_KEY` after a Settings rename).
2. Every `Settings` field that is required (no default) is documented
   in the reference (catches a new env var that was added to code
   but not yet to the operator-facing reference).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic.fields import FieldInfo

from packages.core.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_PATH = REPO_ROOT / "infra" / "env" / "production.env.reference"
DEPLOY_SCRIPT_PATH = REPO_ROOT / "infra" / "scripts" / "deploy_cloud_run.sh"

_KEY_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)=")
_API_ENV_VARS_LINE = re.compile(r'^API_ENV_VARS="([^"]+)"', re.MULTILINE)
_WEB_ENV_VARS_LINE = re.compile(r'web_env_vars="([^"]+)"', re.MULTILINE)


def _settings_alias_for(field_name: str, info: FieldInfo) -> str:
    """Return the env var name Pydantic expects for this Settings field."""
    return info.alias or field_name.upper()


def _parse_reference_keys() -> set[str]:
    keys: set[str] = set()
    for line in REFERENCE_PATH.read_text().splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _KEY_LINE.match(stripped)
        if match:
            keys.add(match.group(1))
    return keys


def _settings_aliases() -> dict[str, FieldInfo]:
    """Map of env-var-name → FieldInfo for every Settings field."""
    return {
        _settings_alias_for(name, info): info
        for name, info in Settings.model_fields.items()
    }


def test_reference_path_exists() -> None:
    assert REFERENCE_PATH.is_file(), (
        f"production.env.reference missing at {REFERENCE_PATH}"
    )


def test_every_documented_env_maps_to_a_settings_field() -> None:
    """Every `KEY=` in the reference must resolve to a Settings alias.

    Catches obsolete names after a rename — e.g. if the reference
    still says `INTEGRATIONS_ENCRYPTION_KEY` but Settings was renamed
    to `ENCRYPTION_KEY`, the operator copy-paste flow silently drops
    the value and integration decryption breaks in production.
    """
    documented = _parse_reference_keys()
    aliases = _settings_aliases()
    extras = documented - set(aliases)
    # A small allow-list of reference-only vars that are documented
    # for operator context but consumed by other surfaces (Next.js
    # web app, Cloud Run image build-args). These are NOT part of
    # the Python Settings contract.
    web_or_build_only = {
        "APP_COMMIT_SHA",  # stamped per deploy, not on Settings
        "NEXT_PUBLIC_API_BASE_URL",
        "NEXT_PUBLIC_API_MOCKING",
        "NEXT_PUBLIC_COMMIT_SHA",
        "NEXT_PUBLIC_ENVIRONMENT",
        "INTERNAL_API_BASE_URL",
    }
    unexpected = extras - web_or_build_only
    assert not unexpected, (
        "production.env.reference documents env vars that do not "
        f"exist on Settings: {sorted(unexpected)}. Either add the "
        "field to packages/core/config.py or remove the line from "
        "production.env.reference."
    )


def test_every_required_settings_field_is_documented() -> None:
    """Every Settings field without a default must be in the reference.

    Catches a new env var added to code but never documented for the
    operator — first prod deploy after the merge would silently use
    the absent value (or crash before boot if no default).
    """
    documented = _parse_reference_keys()
    aliases = _settings_aliases()
    missing: list[str] = []
    for alias, info in aliases.items():
        if info.is_required() and alias not in documented:
            missing.append(alias)
    assert not missing, (
        "Settings fields without defaults are NOT documented in "
        f"production.env.reference: {sorted(missing)}. Add a line "
        "to infra/env/production.env.reference for each."
    )


# Required production contract — env vars that MUST be in the
# reference even when their Settings field has a dev-friendly default.
# Without this list, an operator could delete the line from the
# reference and the other two tests would not catch it (they only
# fire on Settings-side changes, not reference-side deletions).
# Per DEPLOYMENT_RULES.md §4 (no localhost in prod) and §1 (every
# production-required surface must appear in the reference).
REQUIRED_PRODUCTION_CONTRACT = [
    "OAUTH_REDIRECT_BASE_URL",  # OAuth callback base — 127.0.0.1 default
    "WEB_APP_BASE_URL",          # post-OAuth redirect — 127.0.0.1 default
    "SALESFORCE_CALLBACK_URL",   # Salesforce Connected App redirect URI
    "TRACKING_BASE_URL",         # outreach tracking pixel — None default
    "API_CORS_ORIGINS",          # web→API CORS — empty default
    "WEB_CORS_ORIGINS",          # symmetric — empty default
]


@pytest.mark.parametrize("alias", REQUIRED_PRODUCTION_CONTRACT)
def test_required_production_contract_documented(alias: str) -> None:
    """Each prod-required env name MUST appear in the reference.

    These fields all have Settings defaults that are wrong for prod
    (localhost, None, or empty list). The drift this test catches is
    operator-facing: someone removes the line from the reference and
    a future operator setting up prod has no signal that the value
    must be overridden.
    """
    documented = _parse_reference_keys()
    assert alias in documented, (
        f"{alias} is part of the required production env contract and "
        "MUST be in infra/env/production.env.reference even though its "
        "Settings field has a default — the default is dev-only and "
        "leads to a broken prod if the operator misses it."
    )


def _parse_deploy_script_api_env_vars() -> set[str]:
    """Extract the env-var KEY names set on fusion-api by the canonical
    deploy script's `API_ENV_VARS=` line."""
    content = DEPLOY_SCRIPT_PATH.read_text()
    match = _API_ENV_VARS_LINE.search(content)
    if not match:
        return set()
    csv = match.group(1)
    return {pair.split("=", 1)[0] for pair in csv.split(",") if "=" in pair}


def _parse_deploy_script_web_env_vars() -> dict[str, str]:
    """Extract the env vars set on fusion-web by the canonical deploy script."""
    content = DEPLOY_SCRIPT_PATH.read_text()
    match = _WEB_ENV_VARS_LINE.search(content)
    if not match:
        return {}
    csv = match.group(1)
    pairs = [pair for pair in csv.split(",") if "=" in pair]
    return dict(pair.split("=", 1) for pair in pairs)


@pytest.mark.parametrize("alias", REQUIRED_PRODUCTION_CONTRACT)
def test_required_production_contract_in_deploy_script(alias: str) -> None:
    """Each prod-required env name MUST be wired into the canonical
    deploy script's API_ENV_VARS, not just documented in the reference.

    Without this, an operator could see the var in
    `production.env.reference`, confirm `Settings` declares it, and
    still ship a revision missing it (which is exactly the
    `WEB_CORS_ORIGINS` gap Phase 2's `startup.config` log surfaced
    AFTER reference + tests said the contract was complete).
    """
    api_env_keys = _parse_deploy_script_api_env_vars()
    assert alias in api_env_keys, (
        f"{alias} is in REQUIRED_PRODUCTION_CONTRACT but not in "
        "API_ENV_VARS in infra/scripts/deploy_cloud_run.sh. Add it "
        "to the deploy script so every Cloud Run revision boots with "
        "the value set."
    )


def test_web_deploy_script_uses_public_and_internal_api_urls() -> None:
    """fusion-web needs separate public and server-side API URLs.

    `NEXT_PUBLIC_API_BASE_URL` is browser-visible and must stay on the
    public app origin. Next.js server-side route handlers use
    `INTERNAL_API_URL` / `INTERNAL_API_BASE_URL` to reach fusion-api
    directly for proxying and credential resolution.
    """
    web_env = _parse_deploy_script_web_env_vars()
    assert web_env["NEXT_PUBLIC_API_BASE_URL"] == "https://fusioncrm.app"
    assert "INTERNAL_API_URL" in web_env
    assert "INTERNAL_API_BASE_URL" in web_env
    assert web_env["NEXT_PUBLIC_API_MOCKING"] == "disabled"

"""Regression test for deploy-prod api-smoke diagnostic logging.

ENG-178 Phase 4.5: the ``check()`` and ``fail()`` shell helpers inside
the ``api-smoke`` job of ``.github/workflows/deploy-prod.yml`` are
called from command substitutions (``BODY=$(check "/healthz")``).
Anything they write to stdout is captured into the calling variable
and never reaches GitHub Actions logs, so on a smoke failure the
operator saw only a bare non-zero exit with no HTTP status, no
truncated response body, and no ``::error::`` annotation.

The fix is to redirect every diagnostic to stderr while keeping the
response body on stdout for the success path. This test scans the
workflow file and asserts the helpers stay structured that way, so a
later refactor cannot silently swallow diagnostics again.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_PROD_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-prod.yml"


def _smoke_step_script() -> str:
    """Return the inline ``run:`` script body of the api-smoke step.

    The api-smoke job has a step with ``id: smoke`` whose ``run:`` block
    defines ``fail()``/``check()`` and invokes the endpoint checks. We
    only need a string we can grep against, not full YAML semantics, so
    bracket the slice between two unambiguous anchors that already exist
    in the file: the ``id: smoke`` line and the next step header
    (``- name: Auto-rollback on smoke failure``).
    """
    text = DEPLOY_PROD_WORKFLOW.read_text()
    start_match = re.search(r"^\s*id:\s*smoke\s*$", text, re.MULTILINE)
    end_match = re.search(
        r"^\s*- name:\s*Auto-rollback on smoke failure\s*$",
        text,
        re.MULTILINE,
    )
    assert start_match is not None, "api-smoke step (id: smoke) not found"
    assert end_match is not None, "Auto-rollback step header not found"
    assert start_match.end() < end_match.start(), (
        "id: smoke must appear before the Auto-rollback step"
    )
    return text[start_match.end() : end_match.start()]


def test_fail_helper_writes_error_annotation_to_stderr() -> None:
    """``fail()`` must not write its ``::error::`` line to stdout.

    When ``check()`` is called via ``BODY=$(check ...)`` and the inner
    request fails, the call chain reaches ``fail()`` inside the command
    substitution subshell. Without ``>&2`` the annotation is captured
    into BODY and the operator never sees why the smoke failed.
    """
    script = _smoke_step_script()
    assert re.search(
        r'echo\s+"::error::smoke fail:\s*\$1"\s*>&2',
        script,
    ), "fail() must redirect its ::error:: annotation to stderr"


def test_check_helper_sends_failure_diagnostics_to_stderr() -> None:
    """The HTTP-status + body-preview block in ``check()`` must use stderr.

    Otherwise the diagnostic is swallowed by both
    ``BODY=$(check ...)`` and ``check ... >/dev/null`` call sites.
    """
    script = _smoke_step_script()
    diagnostic = re.search(
        r"\{\s*"
        r'echo\s+"HTTP\s+\$\{status\}\s+for\s+\$\{path\};\s*body:"\s*\n'
        r"\s*head\s+-n\s+50\s+/tmp/body\s*\n"
        r"\s*\}\s*>&2",
        script,
    )
    assert diagnostic is not None, (
        "check() must emit HTTP-status + body preview to stderr as a "
        "grouped redirect, not to stdout"
    )


def test_check_helper_still_returns_body_on_stdout() -> None:
    """Success path: ``cat /tmp/body`` (unredirected) so BODY=... works.

    The deep-smoke step parses ``BODY=$(check "/healthz")`` with
    ``python3 -c 'json.load(sys.stdin)'``. If the success-path body
    line is ever redirected, every smoke run breaks even when the API
    is healthy.
    """
    script = _smoke_step_script()
    # Final line of check() must remain a bare ``cat /tmp/body``: no
    # ``>&2``, no ``>/dev/null``, no pipe.
    success_line = re.search(
        r"^\s*cat\s+/tmp/body\s*$",
        script,
        re.MULTILINE,
    )
    assert success_line is not None, (
        "check() must still print the response body on stdout for the "
        "success path so BODY=$(check ...) keeps working"
    )


def test_smoke_token_includes_email_claim() -> None:
    """Smoke token mint MUST pass ``--include-email`` to gcloud.

    Google Cloud IAP rejects an impersonated service-account OIDC token
    without an ``email`` claim. The deep smoke against
    ``https://fusioncrm.app/api/healthz`` can be rejected at the IAP
    edge before the request reaches Cloud Run unless this flag is
    present.

    The token line must keep ``--impersonate-service-account`` and
    ``--audiences`` (the WIF principal requires impersonation; IAP
    requires the pinned client ID as audience) and additionally pass
    ``--include-email`` so the minted token carries ``email`` and
    ``email_verified`` claims.
    """
    script = _smoke_step_script()
    token_block = re.search(
        r'TOKEN="\$\(gcloud\s+auth\s+print-identity-token\s*\\\s*\n'
        r'\s*--impersonate-service-account="\$\{DEPLOYER_SA\}"\s*\\\s*\n'
        r'\s*--audiences="\$\{IAP_AUDIENCE\}"\s*\\\s*\n'
        r"\s*--include-email\)",
        script,
    )
    assert token_block is not None, (
        "smoke token command must invoke ``gcloud auth print-identity-token`` "
        "with --impersonate-service-account, --audiences, and --include-email "
        "(IAP requires the email claim on impersonated SA OIDC tokens)"
    )


def test_rollback_needed_output_is_unchanged() -> None:
    """``fail()`` must still set ``rollback_needed=true`` in GITHUB_OUTPUT.

    Auto-rollback gates on this exact output key. The stderr fix is
    pure logging — it must not change the rollback contract.
    """
    script = _smoke_step_script()
    assert re.search(
        r'echo\s+"rollback_needed=true"\s*>>\s*"\$GITHUB_OUTPUT"',
        script,
    ), "fail() must still write rollback_needed=true to GITHUB_OUTPUT"

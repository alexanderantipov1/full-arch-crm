"""Regression test for the primary-revision filter used by deploy-prod.

ENG-179: ``status.traffic`` on a Cloud Run service is not ordered by
percent. Tagged PR-preview entries (0% traffic) can land before the
untagged 100% primary. A naive ``status.traffic[0]`` read therefore
returns the wrong revision and breaks the post-deploy traffic verifier.

The workflow uses an inline ``python3 -c`` one-liner to pick the actual
primary (first entry with ``percent > 0`` and no ``tag``). This test
runs the same one-liner verbatim against representative fixtures and
asserts the chosen revision. If the filter drifts in the workflow, this
test must drift with it.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

# This is the EXACT one-liner used inside
# ``.github/workflows/deploy-prod.yml`` -> ``Verify traffic is actually
# on the new revision``. Keep them in sync. Any change here MUST be
# mirrored in the workflow and vice versa.
PRIMARY_FILTER_SNIPPET = (
    "import json,sys; "
    "t=json.load(sys.stdin)['status'].get('traffic',[]); "
    "print(next((e['revisionName'] for e in t "
    "if e.get('percent',0)>0 and not e.get('tag')), ''))"
)


def _run_filter(traffic_state: dict) -> str:
    """Run the workflow's filter snippet against a fake ``describe`` payload."""
    # ``sys.executable`` is the running interpreter and
    # ``PRIMARY_FILTER_SNIPPET`` is a module-level literal — no untrusted
    # input flows into this subprocess call.
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", PRIMARY_FILTER_SNIPPET],
        input=json.dumps(traffic_state).encode(),
        check=True,
        capture_output=True,
    )
    return result.stdout.decode().strip()


# Live state observed on fusion-api after ENG-178 merge (2026-05-17,
# deploy-prod run 25981424237). Captured here as the canonical regression
# fixture: tagged 0% entries land before the 100% primary in the API
# response order.
LIVE_FUSION_API_STATE = {
    "status": {
        "traffic": [
            {
                "revisionName": "fusion-api-00049-xiw",
                "tag": "pr-57",
                "url": "https://pr-57---fusion-api-dlsrgczr4q-uw.a.run.app",
            },
            {"percent": 100, "revisionName": "fusion-api-00050-n2s"},
            {
                "revisionName": "fusion-api-00054-jec",
                "tag": "pr-59",
                "url": "https://pr-59---fusion-api-dlsrgczr4q-uw.a.run.app",
            },
            {
                "revisionName": "fusion-api-00095-boc",
                "tag": "pr-68",
                "url": "https://pr-68---fusion-api-dlsrgczr4q-uw.a.run.app",
            },
        ],
    },
}


def test_picks_untagged_primary_when_tag_comes_first() -> None:
    """Reproduces the exact failure mode from deploy-prod run 25981424237."""
    assert _run_filter(LIVE_FUSION_API_STATE) == "fusion-api-00050-n2s"


def test_picks_primary_when_primary_is_first() -> None:
    """Common case: no tagged entries leaking before the primary."""
    state = {
        "status": {
            "traffic": [
                {"percent": 100, "revisionName": "fusion-api-00050-n2s"},
            ],
        },
    }
    assert _run_filter(state) == "fusion-api-00050-n2s"


def test_skips_zero_percent_untagged_entries() -> None:
    """A 0% untagged entry (e.g. an old pinned revision) must not be picked."""
    state = {
        "status": {
            "traffic": [
                {"percent": 0, "revisionName": "fusion-api-00040-old"},
                {"percent": 100, "revisionName": "fusion-api-00050-n2s"},
            ],
        },
    }
    assert _run_filter(state) == "fusion-api-00050-n2s"


def test_returns_empty_string_when_no_untagged_primary() -> None:
    """Defensive: a traffic config with only tagged entries → empty result.

    The workflow already emits a ``::warning::`` and proceeds when the
    auto-rollback target is empty (ENG-175 §A). Mirror that contract
    here so the deploy step fails loudly downstream rather than picking
    a tagged revision by accident.
    """
    state = {
        "status": {
            "traffic": [
                {"revisionName": "fusion-api-00049-xiw", "tag": "pr-57"},
                {"revisionName": "fusion-api-00054-jec", "tag": "pr-59"},
            ],
        },
    }
    assert _run_filter(state) == ""


def test_returns_empty_string_on_empty_traffic() -> None:
    """A brand-new service before its first deploy has no traffic entries."""
    assert _run_filter({"status": {"traffic": []}}) == ""
    assert _run_filter({"status": {}}) == ""


@pytest.mark.parametrize(
    "primary_index",
    [0, 1, 2, 3],
)
def test_picks_primary_regardless_of_order(primary_index: int) -> None:
    """The filter must not depend on the API's traffic-array order."""
    tagged = [
        {"revisionName": f"fusion-api-00099-t{i}", "tag": f"pr-{i}"}
        for i in range(3)
    ]
    primary = {"percent": 100, "revisionName": "fusion-api-00050-n2s"}
    traffic = tagged[:primary_index] + [primary] + tagged[primary_index:]
    state = {"status": {"traffic": traffic}}
    assert _run_filter(state) == "fusion-api-00050-n2s"

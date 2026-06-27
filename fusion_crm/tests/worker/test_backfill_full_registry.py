"""Registry guards for the nightly backfill job (ENG-406).

The nightly Cloud Run job is wired by NAME (deploy_cloud_run.sh passes
``--entities ... merge_split_persons``); a silent rename here would make
the scheduler crash at 10:17 UTC. Pin the registry and the script path
the reconciliation leg loads at runtime.
"""

from __future__ import annotations

from apps.worker.jobs.backfill_full import _ALL_ENTITIES, _ENTITY_RUNNERS


def test_registry_covers_all_entities() -> None:
    assert set(_ALL_ENTITIES) == set(_ENTITY_RUNNERS)


def test_merge_split_persons_is_registered() -> None:
    assert "merge_split_persons" in _ALL_ENTITIES
    assert _ENTITY_RUNNERS["merge_split_persons"].__name__ == (
        "_reconcile_merge_split_persons"
    )


def test_cs_treatments_is_registered() -> None:
    # ENG-551 track B: the deep backfill must cover treatment_procedure so the
    # ENG-551 part-A resolution fix has historical procedures to resolve
    # against. Treatments load before accounting_transactions.
    assert "cs_treatments" in _ALL_ENTITIES
    assert _ENTITY_RUNNERS["cs_treatments"].__name__ == "_backfill_cs_treatments"
    assert _ALL_ENTITIES.index("cs_treatments") < _ALL_ENTITIES.index(
        "cs_accounting_transactions"
    )


def test_reconciliation_script_loads_via_the_legs_own_loader() -> None:
    # Run the EXACT loader the prod leg uses — path resolution AND the
    # importlib/sys.modules dance — so any loading bug fails here instead
    # of at 10:17 UTC in prod.
    from apps.worker.jobs.backfill_full import _load_merge_script

    module = _load_merge_script()
    assert hasattr(module, "run")
    assert hasattr(module, "Buckets")

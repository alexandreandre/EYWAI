"""Tests persistance totaux DSN au commit."""

from unittest.mock import patch

from app.modules.dsn_import.application.cumuls import aggregate_cumuls_by_company_period
from app.modules.dsn_import.application.payroll_totals_persist import (
    build_resolve_company_id_for_totals,
    build_resolve_company_id_from_batch,
    persist_batch_dsn_payroll_totals,
)


def test_build_resolve_company_id_for_totals_uses_target_company():
    resolve = build_resolve_company_id_for_totals(target_company_id="cartol-id")
    assert resolve("95147478200020") == "cartol-id"


def test_build_resolve_company_id_from_batch_uses_establishment_mapping():
    batch_id = "batch-cartol"
    with (
        patch(
            "app.modules.dsn_import.application.payroll_totals_persist.repo.get_batch",
            return_value={"summary": {"target_company_id": "cartol-id"}},
        ),
        patch(
            "app.modules.dsn_import.application.payroll_totals_persist.repo.list_items",
            return_value=[
                {
                    "item_type": "establishment",
                    "target_id": "cartol-id",
                    "mapped_payload": {"siret": "95147478200020"},
                }
            ],
        ),
    ):
        resolve = build_resolve_company_id_from_batch(batch_id)
    assert resolve("95147478200020") == "cartol-id"


def test_aggregate_cumuls_by_company_period():
    items = [
        {
            "item_type": "cumul",
            "mapped_payload": {
                "siret": "80248516900022",
                "period": "2026-01",
                "month_totals": {"brut": 3000.0, "net_imposable": 2400.0, "pas": 100.0},
            },
        },
        {
            "item_type": "cumul",
            "mapped_payload": {
                "siret": "80248516900022",
                "period": "2026-01",
                "month_totals": {
                    "brut": 2500.0,
                    "net_imposable": 2000.0,
                    "pas": 80.0,
                    "employee_charges": 500.0,
                    "employer_charges": 700.0,
                },
            },
        },
    ]
    agg = aggregate_cumuls_by_company_period(
        items, resolve_company_id=lambda siret: "co-1" if siret else None
    )
    assert agg["co-1"]["2026-01"]["gross_salary"] == 5500.0
    assert agg["co-1"]["2026-01"]["employee_count"] == 2
    assert agg["co-1"]["2026-01"]["employees_with_gross"] == 2
    assert agg["co-1"]["2026-01"]["employee_charges"] == 500.0


def test_aggregate_cumuls_ignores_net_without_brut():
    """Le net ne doit pas être agrégé pour les salariés sans brut extrait (DSN partiel)."""
    items = [
        {
            "item_type": "cumul",
            "mapped_payload": {
                "siret": "80248516900022",
                "period": "2026-01",
                "month_totals": {"brut": 3000.0, "net_imposable": 2400.0, "pas": 0.0},
            },
        },
        {
            "item_type": "cumul",
            "mapped_payload": {
                "siret": "80248516900022",
                "period": "2026-01",
                "month_totals": {"brut": 0.0, "net_imposable": 5000.0, "pas": 0.0},
            },
        },
    ]
    agg = aggregate_cumuls_by_company_period(
        items, resolve_company_id=lambda siret: "co-1" if siret else None
    )
    row = agg["co-1"]["2026-01"]
    assert row["gross_salary"] == 3000.0
    assert row["net_imposable"] == 2400.0
    assert row["employee_count"] == 2
    assert row["employees_with_gross"] == 1


def test_aggregate_skips_inferred_pat_when_partial():
    items = [
        {
            "item_type": "cumul",
            "mapped_payload": {
                "siret": "80248516900022",
                "period": "2026-05",
                "month_totals": {
                    "brut": 1000.0,
                    "net_imposable": 780.0,
                    "pas": 0.0,
                    "employee_charges": 220.0,
                    "employer_charges": 0.0,
                },
            },
        },
        {
            "item_type": "cumul",
            "mapped_payload": {
                "siret": "80248516900022",
                "period": "2026-05",
                "month_totals": {"brut": 0.0, "net_imposable": 100.0, "pas": 0.0},
            },
        },
    ]
    agg = aggregate_cumuls_by_company_period(
        items, resolve_company_id=lambda siret: "co-1" if siret else None
    )
    row = agg["co-1"]["2026-05"]
    assert row["employee_count"] == 2
    assert row["employees_with_gross"] == 1
    assert row["employer_charges"] == 0.0


def test_aggregate_low_brut_cluster_triggers_reliable_mode():
    """Plusieurs bruts résiduels (< 700 €) → agrégation en mode fiable (DSN partiel)."""
    items = []
    for idx in range(11):
        items.append(
            {
                "item_type": "cumul",
                "mapped_payload": {
                    "siret": "79817109600034",
                    "period": "2026-05",
                    "month_totals": {
                        "brut": 500.0,
                        "net_imposable": 400.0,
                        "pas": 0.0,
                    },
                },
            }
        )
    for idx in range(89):
        items.append(
            {
                "item_type": "cumul",
                "mapped_payload": {
                    "siret": "79817109600034",
                    "period": "2026-05",
                    "month_totals": {
                        "brut": 1000.0,
                        "net_imposable": 780.0,
                        "pas": 0.0,
                    },
                },
            }
        )
    agg = aggregate_cumuls_by_company_period(
        items, resolve_company_id=lambda siret: "co-1" if siret else None
    )
    row = agg["co-1"]["2026-05"]
    assert row["employee_count"] == 100
    assert row["employees_with_gross"] == 89
    assert row["gross_salary"] == 89000.0
    assert row["employer_charges"] == 0.0


def test_aggregate_infers_pat_when_complete():
    items = [
        {
            "item_type": "cumul",
            "mapped_payload": {
                "siret": "53438649500053",
                "period": "2026-05",
                "month_totals": {
                    "brut": 1000.0,
                    "net_imposable": 780.0,
                    "pas": 0.0,
                    "employee_charges": 220.0,
                    "employer_charges": 0.0,
                },
            },
        },
    ]
    agg = aggregate_cumuls_by_company_period(
        items, resolve_company_id=lambda siret: "co-1" if siret else None
    )
    assert agg["co-1"]["2026-05"]["employer_charges"] > 0


def test_aggregate_cumuls_fallback_employee_charges():
    items = [
        {
            "item_type": "cumul",
            "mapped_payload": {
                "siret": "80248516900022",
                "period": "2026-03",
                "month_totals": {"brut": 24049.34, "net_imposable": 19547.93, "pas": 0.0},
            },
        },
    ]
    agg = aggregate_cumuls_by_company_period(
        items, resolve_company_id=lambda siret: "co-1" if siret else None
    )
    assert agg["co-1"]["2026-03"]["employee_charges"] == round(24049.34 - 19547.93, 2)


def test_persist_batch_dsn_payroll_totals():
    items = [
        {
            "item_type": "cumul",
            "mapped_payload": {
                "siret": "80248516900022",
                "period": "2026-02",
                "month_totals": {"brut": 1000.0, "net_imposable": 800.0, "pas": 0.0},
            },
        }
    ]
    with patch(
        "app.modules.dsn_import.application.payroll_totals_persist.totals_repo.upsert_totals"
    ) as upsert:
        counts = persist_batch_dsn_payroll_totals(
            items,
            resolve_company_id=lambda _: "co-1",
            batch_id="batch-1",
        )
    assert counts == {"co-1": 1}
    upsert.assert_called_once()
    kwargs = upsert.call_args.kwargs
    assert kwargs["gross_salary"] == 1000.0
    assert kwargs["employee_charges"] == 200.0
    assert kwargs["last_batch_id"] == "batch-1"

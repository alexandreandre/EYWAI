"""Tests couverture DSN par entreprise."""

from datetime import date

from app.modules.dsn_import.application.coverage import (
    compute_coverage,
    expected_last_period,
    merge_dsn_alerts_into_overview,
)


def test_expected_last_period_before_grace():
    company = {"paie_occurrence": 25}
    ref = date(2026, 6, 16)
    assert expected_last_period(company, ref) == "2026-05"


def test_compute_coverage_native_not_applicable():
    company = {
        "id": "c1",
        "dsn_sync_mode": "native",
        "siret": "95147478200020",
        "siren": "951474782",
    }
    cov = compute_coverage(company, batches=[])
    assert cov["status"] == "not_applicable"
    assert cov["alerts"] == []


def test_compute_coverage_never_imported():
    company = {
        "id": "c1",
        "dsn_sync_mode": "external",
        "siret": "95147478200020",
        "siren": "951474782",
    }
    cov = compute_coverage(company, batches=[], reference=date(2026, 6, 16))
    assert cov["status"] == "never"
    assert any(a["code"] == "dsn_never_imported" for a in cov["alerts"])


def test_merge_dsn_alerts_rh_copy():
    alerts = merge_dsn_alerts_into_overview(
        [],
        {
            "alerts": [
                {
                    "code": "dsn_month_missing",
                    "severity": "warning",
                    "expected_period": "2026-05",
                }
            ]
        },
    )
    assert "2026-05" in alerts[0]["label"]
    assert alerts[0]["action"] == "contact_admin"


def test_compute_admin_coverage_matrix():
    from app.modules.dsn_import.application.coverage import compute_admin_coverage_matrix

    companies = [
        {
            "id": "c1",
            "company_name": "Alpha",
            "dsn_sync_mode": "external",
            "siret": "11111111100011",
            "siren": "111111111",
            "group_name": "G1",
        },
        {
            "id": "c2",
            "company_name": "Beta",
            "dsn_sync_mode": "native",
            "siret": "22222222200022",
            "siren": "222222222",
            "group_name": "G1",
        },
    ]
    batches = [
        {
            "id": "b1",
            "status": "committed",
            "siren": "111111111",
            "period_min": "2026-01",
            "period_max": "2026-01",
            "summary": {
                "commit_report": {"target_company_id": "c1"},
                "periods_committed": ["2026-01"],
            },
            "created_at": "2026-02-01T00:00:00Z",
        }
    ]
    matrix = compute_admin_coverage_matrix(companies, year=2026, batches=batches)
    assert matrix["year"] == 2026
    assert len(matrix["companies"]) == 2
    alpha = next(c for c in matrix["companies"] if c["company_id"] == "c1")
    beta = next(c for c in matrix["companies"] if c["company_id"] == "c2")
    assert "2026-01" in alpha["months_covered"]
    assert len(alpha["timeline"]) == 12
    assert beta["status"] == "missing"


def test_compute_coverage_excludes_revoked_periods():
    company = {
        "id": "c1",
        "dsn_sync_mode": "external",
        "siret": "11111111100011",
        "siren": "111111111",
    }
    batches = [
        {
            "id": "b1",
            "status": "committed",
            "siren": "111111111",
            "period_min": "2026-01",
            "period_max": "2026-02",
            "summary": {
                "commit_report": {"target_company_id": "c1"},
                "periods_committed": ["2026-01", "2026-02"],
            },
            "created_at": "2026-03-01T00:00:00Z",
        }
    ]
    cov = compute_coverage(
        company,
        batches=batches,
        reference=date(2026, 6, 16),
        revoked_periods=["2026-02"],
    )
    assert "2026-01" in cov["months_covered"]
    assert "2026-02" not in cov["months_covered"]
    feb = next(m for m in cov["timeline"] if m["period"] == "2026-02")
    assert feb["state"] == "missing"

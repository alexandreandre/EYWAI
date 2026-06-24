"""Tests couverture DSN par entreprise."""

from datetime import date

from app.modules.dsn_import.application.coverage import (
    compute_coverage,
    count_timeline_coverage,
    expected_last_period,
    is_dsn_coverage_complete,
    merge_dsn_alerts_into_overview,
    resolve_next_import_period,
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


def test_resolve_next_import_period_first_missing():
    cov = {
        "timeline": [
            {"period": "2026-01", "state": "missing"},
            {"period": "2026-02", "state": "missing"},
            {"period": "2026-06", "state": "future"},
        ],
        "gaps": [],
    }
    assert resolve_next_import_period(cov) == "2026-01"


def test_compute_coverage_includes_next_import_period():
    company = {
        "id": "c1",
        "dsn_sync_mode": "external",
        "siret": "11111111100011",
        "siren": "111111111",
    }
    cov = compute_coverage(company, batches=[], reference=date(2026, 6, 16))
    assert cov["next_import_period"] == "2026-01"


def test_count_timeline_coverage_and_complete():
    coverage = {
        "status": "ok",
        "timeline": [
            {"period": "2026-01", "state": "covered"},
            {"period": "2026-02", "state": "covered"},
            {"period": "2026-03", "state": "missing"},
            {"period": "2026-04", "state": "future"},
        ],
    }
    covered, total = count_timeline_coverage(coverage)
    assert covered == 2
    assert total == 3
    assert is_dsn_coverage_complete(coverage) is True

    coverage["status"] = "missing"
    assert is_dsn_coverage_complete(coverage) is False

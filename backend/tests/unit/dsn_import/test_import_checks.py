"""Tests contrôles sémantiques import DSN."""

from unittest.mock import patch

from app.modules.dsn_import.application.import_checks import (
    attach_import_context_warnings,
    company_names_semantically_match,
    format_period_fr,
    strip_import_context_warnings,
)


def _cov(*, expected: str, months_covered: list, gaps: list, timeline: list):
    return {
        "expected_last_period": expected,
        "months_covered": months_covered,
        "gaps": gaps,
        "timeline": timeline,
    }


def test_company_names_semantically_match_variants():
    assert company_names_semantically_match("Cartol Industrie", "CARTOL INDUSTRIE SAS")
    assert company_names_semantically_match("LEWIS", "Lewis Industries")
    assert not company_names_semantically_match("Cartol Industrie", "Colorplast")


def test_format_period_fr():
    assert format_period_fr("2026-03") == "mars 2026"


def test_attach_period_mismatch_when_unintended():
    anomalies: list = []
    summary: dict = {"siret": "95147478200020", "period_min": "2026-03", "period_max": "2026-03"}
    company = {
        "id": "c1",
        "company_name": "Cartol Industrie",
        "siret": "95147478200020",
        "dsn_sync_mode": "transition",
    }

    with patch(
        "app.modules.dsn_import.application.import_checks.repo.find_company_by_id",
        return_value=company,
    ), patch(
        "app.modules.dsn_import.application.coverage.compute_coverage",
        return_value=_cov(
            expected="2026-05",
            months_covered=["2026-01"],
            gaps=["2026-02"],
            timeline=[
                {"period": "2026-01", "state": "covered"},
                {"period": "2026-02", "state": "missing"},
                {"period": "2026-03", "state": "missing"},
            ],
        ),
    ):
        attach_import_context_warnings(
            anomalies,
            summary,
            mode="monthly",
            target_company_id="c1",
            periods=["2026-03"],
            dsn_company_name="CARTOL INDUSTRIE",
            intended_period="2026-02",
        )

    types = {a["type"] for a in anomalies}
    assert "period_mismatch" in types
    assert "intended_period_mismatch" in types
    assert "company_name_mismatch" not in types


def test_skip_period_mismatch_when_user_chose_detected_month():
    anomalies: list = []
    summary: dict = {"siret": "111", "period_min": "2026-02", "period_max": "2026-02"}
    company = {"id": "c1", "company_name": "Cartol", "siret": "111", "dsn_sync_mode": "transition"}

    with patch(
        "app.modules.dsn_import.application.import_checks.repo.find_company_by_id",
        return_value=company,
    ), patch(
        "app.modules.dsn_import.application.coverage.compute_coverage",
        return_value=_cov(
            expected="2026-05",
            months_covered=["2026-01"],
            gaps=["2026-02", "2026-03", "2026-04", "2026-05"],
            timeline=[
                {"period": "2026-01", "state": "covered"},
                {"period": "2026-02", "state": "missing"},
            ],
        ),
    ):
        attach_import_context_warnings(
            anomalies,
            summary,
            mode="monthly",
            target_company_id="c1",
            periods=["2026-02"],
            intended_period="2026-02",
        )

    assert not any(a["type"] == "period_mismatch" for a in anomalies)


def test_skip_period_mismatch_when_reimporting_covered_month():
    """Réimport d'un mois déjà couvert : pas d'avertissement period_mismatch parasite."""
    anomalies: list = []
    summary: dict = {"siret": "111", "period_min": "2026-03", "period_max": "2026-03"}
    company = {"id": "c1", "company_name": "Cartol", "siret": "111", "dsn_sync_mode": "transition"}

    with patch(
        "app.modules.dsn_import.application.import_checks.repo.find_company_by_id",
        return_value=company,
    ), patch(
        "app.modules.dsn_import.application.coverage.compute_coverage",
        return_value=_cov(
            expected="2026-04",
            months_covered=["2026-01", "2026-02", "2026-03"],
            gaps=[],
            timeline=[
                {"period": "2026-03", "state": "covered"},
                {"period": "2026-04", "state": "missing"},
            ],
        ),
    ):
        attach_import_context_warnings(
            anomalies,
            summary,
            mode="monthly",
            target_company_id="c1",
            periods=["2026-03"],
            intended_period="2026-03",
        )

    assert not any(a["type"] == "period_mismatch" for a in anomalies)


def test_period_mismatch_uses_next_import_when_no_intended_period():
    anomalies: list = []
    summary: dict = {"siret": "111", "period_min": "2026-02", "period_max": "2026-02"}
    company = {"id": "c1", "company_name": "Comitech", "siret": "111", "dsn_sync_mode": "transition"}

    with patch(
        "app.modules.dsn_import.application.import_checks.repo.find_company_by_id",
        return_value=company,
    ), patch(
        "app.modules.dsn_import.application.coverage.compute_coverage",
        return_value=_cov(
            expected="2026-05",
            months_covered=[],
            gaps=[],
            timeline=[
                {"period": "2026-01", "state": "missing"},
                {"period": "2026-02", "state": "missing"},
            ],
        ),
    ):
        attach_import_context_warnings(
            anomalies,
            summary,
            mode="monthly",
            target_company_id="c1",
            periods=["2026-02"],
        )

    assert any(a["type"] == "period_mismatch" for a in anomalies)
    assert summary["next_import_period"] == "2026-01"


def test_attach_company_name_mismatch():
    anomalies: list = []
    summary: dict = {"siret": "111", "period_min": "2026-01", "period_max": "2026-01"}
    company = {"id": "c1", "company_name": "Colorplast", "siret": "111"}

    with patch(
        "app.modules.dsn_import.application.import_checks.repo.find_company_by_id",
        return_value=company,
    ), patch(
        "app.modules.dsn_import.application.coverage.compute_coverage",
        return_value=_cov(
            expected="2026-01",
            months_covered=[],
            gaps=[],
            timeline=[{"period": "2026-01", "state": "missing"}],
        ),
    ):
        attach_import_context_warnings(
            anomalies,
            summary,
            mode="monthly",
            target_company_id="c1",
            periods=["2026-01"],
            dsn_company_name="Cartol Industrie SAS",
        )

    assert any(a["type"] == "company_name_mismatch" for a in anomalies)


def test_strip_import_context_warnings():
    anomalies = [
        {"type": "period_mismatch", "severity": "warning"},
        {"type": "duplicate_period", "severity": "warning"},
    ]
    out = strip_import_context_warnings(anomalies)
    assert len(out) == 1
    assert out[0]["type"] == "duplicate_period"

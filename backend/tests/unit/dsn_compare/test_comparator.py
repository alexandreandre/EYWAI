"""Tests comparateur DSN."""

from __future__ import annotations

from pathlib import Path

from app.modules.dsn_compare.application.comparator import compare_dsn_bytes
from app.modules.dsn_compare.application.report_writer import (
    report_to_json,
    report_to_markdown,
)
from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
from app.modules.dsn_export.domain.writer import encode_dsn_bytes

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "dsn_export"
    / "fixtures"
    / "sample_p26_minimal.txt"
)


def test_compare_identical_files_is_parfait():
    content = FIXTURE.read_bytes()
    report = compare_dsn_bytes(content, content, reference_name="a.dsn", actual_name="b.dsn")
    assert report.establishments
    est = report.establishments[0]
    assert est.matched_count >= 1
    assert all(ln.verdict in {"PARFAIT", "OK"} for ln in est.summary_lines)
    emp = est.employees[0]
    assert emp.overall_verdict in {"PARFAIT", "OK"}
    md = report_to_markdown(report)
    assert "Comparaison DSN" in md
    assert report_to_json(report)


def test_compare_detects_brut_anomaly():
    company = {
        "siret": "12345678900015",
        "name": "ACME INDUSTRIE",
        "code_naf": "2562B",
        "address": {"rue": "1 RUE DE LA PAIX", "code_postal": "75001", "ville": "PARIS"},
    }
    row = {
        "employee": {
            "first_name": "Jean",
            "last_name": "Dupont",
            "nir": "1850175123456",
            "sexe": "M",
            "date_naissance": "1985-01-15",
            "contract_type": "CDI",
            "hire_date": "2020-01-01",
            "statut": "Non-Cadre",
            "adresse": {"rue": "10 AV", "code_postal": "75010", "ville": "PARIS"},
        },
        "payslip_data": {
            "salaire_brut": 2500.0,
            "heures_remunerees": 151.67,
            "synthese_net": {
                "net_imposable": 2000.0,
                "net_a_payer": 1850.0,
                "impot_prelevement_a_la_source": {
                    "montant": 100.0,
                    "taux": 5.0,
                    "base": 2000.0,
                },
            },
            "structure_cotisations": {
                "cotisations": [
                    {
                        "coti_id": "securite_sociale_maladie",
                        "base": 2500,
                        "montant_patronal": 175,
                        "taux_patronal": 7,
                    }
                ]
            },
        },
    }
    ref_file, _ = build_parsed_dsn_from_payroll(company, [row], "2026-01")
    row2 = {
        **row,
        "payslip_data": {
            **row["payslip_data"],
            "salaire_brut": 2600.0,
        },
    }
    act_file, _ = build_parsed_dsn_from_payroll(company, [row2], "2026-01")
    report = compare_dsn_bytes(
        encode_dsn_bytes(ref_file),
        encode_dsn_bytes(act_file),
    )
    est = report.establishments[0]
    brut_line = next(ln for ln in est.summary_lines if ln.field == "brut")
    assert brut_line.verdict == "ANOMALIE"
    assert abs(brut_line.delta - 100.0) < 0.01

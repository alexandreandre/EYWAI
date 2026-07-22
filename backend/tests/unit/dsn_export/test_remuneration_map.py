"""Tests ventilation rémunération DSN depuis calcul_du_brut."""

from __future__ import annotations

from app.modules.dsn_export.domain.remuneration_map import (
    analyze_calcul_du_brut,
    build_remunerations_from_payslip,
)


def _payslip_feb_like():
    return {
        "salaire_brut": 2455.03,
        "calcul_du_brut": [
            {"libelle": "Salaire de base", "gain": 1964.0, "quantite": 151.67},
            {
                "libelle": "Heures suppl. structurelles majorées à 25%",
                "gain": 280.51,
                "quantite": 17.33,
            },
            {
                "libelle": "SOUS-TOTAL SALAIRE CONTRACTUEL",
                "gain": 2244.51,
                "quantite": 169.0,
                "is_sous_total": True,
            },
            {
                "libelle": "Heures suppl. majorées à 25%",
                "gain": 56.65,
                "quantite": 3.5,
            },
            {
                "libelle": "Prime d'ancienneté (4 ans, 2 %)",
                "gain": 53.87,
                "quantite": 2244.51,
            },
            {"libelle": "Prime exceptionnelle", "gain": 100.0},
        ],
    }


def test_analyze_calcul_maps_hs_types():
    parts = analyze_calcul_du_brut(_payslip_feb_like())
    assert parts["sous_total_contractuel"] == 2244.51
    assert parts["hs_structurelles_montant"] == 280.51
    assert parts["hs_structurelles_heures"] == 17.33
    assert parts["hs_aleatoires_montant"] == 56.65
    assert parts["hs_aleatoires_heures"] == 3.5


def test_build_remunerations_cegid_shape():
    result = build_remunerations_from_payslip(
        _payslip_feb_like(),
        brut=2455.03,
        period_start="01022026",
        period_end="28022026",
        period="2026-02",
    )
    by_type = {r.type_code: r for r in result.remunerations}
    assert set(by_type) == {"001", "002", "003", "010", "017", "018", "028", "029"}
    assert by_type["001"].montant == 2455.03
    assert by_type["001"].heures == 0.0
    assert by_type["010"].montant == 2244.51
    assert by_type["017"].montant == 56.65
    assert by_type["017"].heures == 3.5
    assert by_type["018"].montant == 280.51
    assert by_type["018"].heures == 17.33
    assert by_type["003"].montant == 2455.03
    assert abs(result.heures_activite - 172.5) < 0.01
    assert len(result.activites) == 2
    assert result.activites[0]["unite"] == "40"
    assert result.activites[0]["mesure"] == 28


def test_builder_emits_full_remu_types():
    from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll

    company = {
        "siret": "12345678900015",
        "name": "ACME",
        "code_naf": "2562B",
        "address": {"rue": "1 RUE", "code_postal": "75001", "ville": "PARIS"},
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
        },
        "payslip_data": {
            **_payslip_feb_like(),
            "net_a_payer": 1622.28,
            "synthese_net": {
                "net_imposable": 1693.42,
                "impot_prelevement_a_la_source": {
                    "montant": 27.09,
                    "taux": 1.6,
                    "base": 1693.42,
                },
            },
        },
    }
    dsn, warnings = build_parsed_dsn_from_payroll(company, [row], "2026-02")
    ver = dsn.etablissement.individus[0].contrats[0].versements[0]
    assert {r.type_code for r in ver.remunerations} >= {
        "001",
        "002",
        "003",
        "010",
        "017",
        "018",
        "028",
        "029",
    }
    assert abs(ver.net_verse - 1622.28) < 0.01
    assert not any("Brut ≤ 0" in w for w in warnings)


def test_skip_zero_brut_employee():
    from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll

    company = {
        "siret": "12345678900015",
        "name": "ACME",
        "code_naf": "2562B",
        "address": {"rue": "1 RUE", "code_postal": "75001", "ville": "PARIS"},
    }
    ok = {
        "employee": {
            "first_name": "A",
            "last_name": "OK",
            "nir": "1850175123456",
            "sexe": "M",
            "date_naissance": "1985-01-15",
            "contract_type": "CDI",
            "hire_date": "2020-01-01",
            "statut": "Non-Cadre",
        },
        "payslip_data": {
            "salaire_brut": 1000.0,
            "net_a_payer": 800.0,
            "synthese_net": {"net_imposable": 850.0},
            "calcul_du_brut": [
                {"libelle": "Salaire de base", "gain": 1000.0, "quantite": 151.67}
            ],
        },
    }
    zero = {
        "employee": {
            "first_name": "B",
            "last_name": "ZERO",
            "nir": "2850175123456",
            "sexe": "F",
            "date_naissance": "1985-01-15",
            "contract_type": "CDI",
            "hire_date": "2020-01-01",
            "statut": "Non-Cadre",
        },
        "payslip_data": {"salaire_brut": -10.0, "synthese_net": {"net_imposable": 0}},
    }
    dsn, warnings = build_parsed_dsn_from_payroll(company, [ok, zero], "2026-01")
    assert len(dsn.etablissement.individus) == 1
    assert any("brut ≤ 0" in w.lower() for w in warnings)

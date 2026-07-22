"""Tests mapping cotisations EYWAI → codes DSN."""

from __future__ import annotations

import pytest

from app.modules.dsn_export.domain.cotisation_mapping import (
    CotisationMappingError,
    build_bases_and_cotisations,
    resolve_dsn_cotisation_code,
)


def test_resolve_known_coti_ids():
    assert resolve_dsn_cotisation_code("securite_sociale_maladie") == "075"
    assert resolve_dsn_cotisation_code("at_mp") == "045"
    assert resolve_dsn_cotisation_code("ags") == "048"
    assert resolve_dsn_cotisation_code("fnal") == "049"
    assert resolve_dsn_cotisation_code("csa") == "068"
    assert resolve_dsn_cotisation_code("allocations_familiales") == "074"
    assert resolve_dsn_cotisation_code("mutuelle") == "059"
    assert resolve_dsn_cotisation_code("reduction_generale") == "018"
    assert resolve_dsn_cotisation_code("reduction_hs_salariale") == "114"
    assert resolve_dsn_cotisation_code("deduction_hs_patronale") == "021"
    assert resolve_dsn_cotisation_code("retraite_comp_t1") == "131"
    assert resolve_dsn_cotisation_code("csg_deductible") == "142"


def test_resolve_from_libelle():
    assert resolve_dsn_cotisation_code(None, "CSG déductible") == "142"
    assert resolve_dsn_cotisation_code(None, "Assurance chômage") == "040"


def test_build_bases_and_cotisations_require_code():
    with pytest.raises(CotisationMappingError):
        build_bases_and_cotisations(
            [{"libelle": "Cotisation mystère", "montant_patronal": 10, "base": 100}],
            brut=100,
            period_start="01012026",
            period_end="31012026",
            require_codes=True,
        )


def test_build_bases_and_cotisations_ok():
    bases, cots, warnings = build_bases_and_cotisations(
        [
            {
                "coti_id": "securite_sociale_maladie",
                "base": 2500,
                "montant_patronal": 175,
                "taux_patronal": 0.07,
            },
            {
                "coti_id": "ags",
                "base": 2500,
                "montant_patronal": 6.25,
                "taux_patronal": 0.0025,
            },
            {
                "coti_id": "retraite_comp_t1",
                "base": 2500,
                "montant_salarial": 80,
                "montant_patronal": 120,
            },
            {
                "coti_id": "ceg_t1",
                "base": 2500,
                "montant_salarial": 20,
                "montant_patronal": 30,
            },
        ],
        brut=2500,
        period_start="01012026",
        period_end="31012026",
        default_ops="79484650100011",
    )
    assert any(b.code == "02" for b in bases)
    assert any(b.code == "03" for b in bases)
    codes = {c.code for c in cots}
    assert "075" in codes
    assert "048" in codes
    assert "131" in codes
    # Retraite unifiée agrégée
    cot_131 = next(c for c in cots if c.code == "131")
    assert abs((cot_131.montant_salarial or 0) + (cot_131.montant_patronal or 0) - 250) < 0.01
    assert warnings == []
    # Taux DSN en %
    ags = next(c for c in cots if c.code == "048")
    assert ags.rubriques.get("S21.G00.81.007") == "0.250"
    assert ags.rubriques.get("S21.G00.81.002") == "79484650100011"

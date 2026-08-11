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
    # La CSG se déclare en 072. Ce test affirmait 142 jusqu'au 09/08/2026 : or
    # 142 est la part patronale Agirc-Arrco de tranche 1 (cahier technique
    # NEODeS CT2026.1.2). Toute la CSG salariale partait donc gonfler la ligne
    # de retraite complémentaire.
    assert resolve_dsn_cotisation_code("csg_deductible") == "072"
    assert resolve_dsn_cotisation_code("csg_non_deductible") == "072"
    assert resolve_dsn_cotisation_code("crds") == "079"
    # Même erreur sur ces deux-là : 093 est la contribution sur indemnités de
    # rupture, et l'Apec a son propre code.
    assert resolve_dsn_cotisation_code("forfait_social") == "071"
    assert resolve_dsn_cotisation_code("apec") == "132"


def test_resolve_from_libelle():
    assert resolve_dsn_cotisation_code(None, "CSG déductible") == "072"
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


def test_pas_plus_de_bases_31_que_d_affiliations():
    """Un 78.005 sans bloc 70 correspondant est refusé (CCH-11/CCH-12) : le
    surplus de lignes 059 se replie sur la dernière affiliation, montants
    additionnés — une base 31 par affiliation, comme le cabinet."""
    bases, cots, _ = build_bases_and_cotisations(
        [
            {"coti_id": "mutuelle", "base": 2500, "montant_patronal": 58.48},
            {"coti_id": "mutuelle", "base": 2500, "montant_patronal": 87.71},
            {"coti_id": "mutuelle", "base": 2500, "montant_patronal": 23.92},
            {"coti_id": "mutuelle", "base": 2500, "montant_patronal": 200.24},
        ],
        brut=2500,
        period_start="01052026",
        period_end="31052026",
        affiliation_ids=["1", "2"],
    )
    bases_31 = [b for b in bases if b.rubriques.get("S21.G00.78.001") == "31"]
    assert [b.rubriques["S21.G00.78.005"] for b in bases_31] == ["1", "2"]
    montants_059 = [
        c.montant_patronal for c in cots if c.rubriques.get("S21.G00.81.001") == "059"
    ]
    assert montants_059 == [58.48, round(87.71 + 23.92 + 200.24, 2)]


def test_chaque_affiliation_recoit_sa_base_31_meme_sans_cotisation():
    """Plus d'affiliations que de lignes 059 : les restantes reçoivent une
    base et une cotisation à zéro (CCH-13), le manque du moteur reste visible."""
    bases, cots, _ = build_bases_and_cotisations(
        [{"coti_id": "mutuelle", "base": 2500, "montant_patronal": 58.48}],
        brut=2500,
        period_start="01052026",
        period_end="31052026",
        affiliation_ids=["1", "2"],
    )
    bases_31 = [b for b in bases if b.rubriques.get("S21.G00.78.001") == "31"]
    assert [b.rubriques["S21.G00.78.005"] for b in bases_31] == ["1", "2"]

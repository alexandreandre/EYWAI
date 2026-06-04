"""Régime intérim (IFM + ICCP) et mandataire social (exclusion chômage/AGS)."""

from __future__ import annotations

import copy
from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations

from .fixtures.baremes_snapshot import baremes_snapshot
from .helpers import build_test_contexte


def _lignes_gain(res):
    return {l["libelle"]: l["gain"] for l in res["lignes_composants_brut"] if l.get("gain")}


def test_interim_ifm_et_iccp_fin_mission():
    ctx = build_test_contexte(
        salaire_base=2000.0,
        type_contrat="Intérim",
        date_entree="2026-01-01",
        date_fin_contrat="2026-03-31",
        cumuls={"brut_total": 4000.0},
        specificites_extra={"is_interim": True},
    )
    assert ctx.is_interim is True
    res = calculer_salaire_brut(ctx, [], date(2026, 3, 1), date(2026, 3, 31), [])
    gains = _lignes_gain(res)
    ifm = next((v for k, v in gains.items() if "fin de mission" in k), None)
    iccp = next((v for k, v in gains.items() if "compensatrice de congés" in k), None)
    assert ifm == pytest.approx(600.0, abs=0.05)  # 10 % de (4000+2000)
    assert iccp == pytest.approx(660.0, abs=0.05)  # 10 % de (4000+2000+600)


def test_interim_pas_ifm_hors_dernier_mois():
    ctx = build_test_contexte(
        salaire_base=2000.0,
        type_contrat="Intérim",
        date_entree="2026-01-01",
        date_fin_contrat="2026-06-30",
        cumuls={"brut_total": 4000.0},
        specificites_extra={"is_interim": True},
    )
    res = calculer_salaire_brut(ctx, [], date(2026, 3, 1), date(2026, 3, 31), [])
    gains = _lignes_gain(res)
    assert not any("fin de mission" in k for k in gains)


def test_mandataire_exclu_assurance_chomage():
    baremes = copy.deepcopy(baremes_snapshot())
    baremes["cotisations"]["cotisations"].append(
        {
            "id": "assurance_chomage",
            "libelle": "Assurance chômage",
            "base": "brut",
            "salarial": None,
            "patronal": 0.0405,
        }
    )
    ctx_normal = build_test_contexte(statut="Cadre", salaire_base=3000.0, baremes=baremes)
    lignes_n, _ = calculer_cotisations(ctx_normal, 3000.0, 0, 0)
    assert any("hômage" in l.get("libelle", "") for l in lignes_n)

    ctx_mand = build_test_contexte(
        statut="Cadre",
        salaire_base=3000.0,
        baremes=baremes,
        specificites_extra={"is_mandataire": True},
    )
    assert ctx_mand.is_mandataire is True
    lignes_m, _ = calculer_cotisations(ctx_mand, 3000.0, 0, 0)
    assert not any("hômage" in l.get("libelle", "") for l in lignes_m)

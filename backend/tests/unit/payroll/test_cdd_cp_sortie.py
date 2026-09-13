"""Indemnité compensatrice de congés payés (ICCP) au dernier mois d'un CDD."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

from .helpers import build_test_contexte


def _lignes_gain(res):
    return {l["libelle"]: l["gain"] for l in res["lignes_composants_brut"] if l.get("gain")}


def test_iccp_cdd_dernier_mois():
    ctx = build_test_contexte(
        salaire_base=2200.0,
        type_contrat="CDD",
        date_entree="2025-10-01",
        date_fin_contrat="2026-04-30",
        cumuls={"brut_total": 8800.0},
    )
    res = calculer_salaire_brut(ctx, [], date(2026, 4, 1), date(2026, 4, 30), [])
    gains = _lignes_gain(res)
    assert "Prime de précarité (CDD)" in gains
    iccp = next(
        (v for k, v in gains.items() if "compensatrice de congés" in k), None
    )
    assert iccp is not None
    # Précarité = 10 % de (8800 + 2200) = 1100 ; ICCP = 10 % de (8800+2200+1100).
    assert gains["Prime de précarité (CDD)"] == pytest.approx(1100.0, abs=0.05)
    assert iccp == pytest.approx(1210.0, abs=0.05)


def test_iccp_absente_si_pas_dernier_mois():
    ctx = build_test_contexte(
        salaire_base=2200.0,
        type_contrat="CDD",
        date_entree="2025-10-01",
        date_fin_contrat="2026-08-31",
        cumuls={"brut_total": 8800.0},
    )
    res = calculer_salaire_brut(ctx, [], date(2026, 4, 1), date(2026, 4, 30), [])
    gains = _lignes_gain(res)
    assert not any("compensatrice de congés" in k for k in gains)
    assert "Prime de précarité (CDD)" not in gains


def test_iccp_desactivable_par_flag():
    ctx = build_test_contexte(
        salaire_base=2200.0,
        type_contrat="CDD",
        date_entree="2025-10-01",
        date_fin_contrat="2026-04-30",
        cumuls={"brut_total": 8800.0},
        specificites_extra={"cdd_sans_iccp": True},
    )
    res = calculer_salaire_brut(ctx, [], date(2026, 4, 1), date(2026, 4, 30), [])
    gains = _lignes_gain(res)
    assert not any("compensatrice de congés" in k for k in gains)
    # La précarité reste due.
    assert "Prime de précarité (CDD)" in gains


def test_iccp_absente_si_sortie_en_attente():
    ctx = build_test_contexte(
        salaire_base=2200.0,
        type_contrat="CDD",
        date_entree="2025-10-01",
        date_fin_contrat="2026-04-30",
        cumuls={"brut_total": 8800.0},
    )
    ctx.block_iccp_cdd = True
    res = calculer_salaire_brut(ctx, [], date(2026, 4, 1), date(2026, 4, 30), [])
    gains = _lignes_gain(res)
    assert not any("compensatrice de congés" in k for k in gains)


def test_iccp_presente_si_le_dossier_de_depart_n_en_porte_pas():
    """Un dossier sans ICCP (préavis nul, licenciement nul) ne fait pas
    taire celle du contrat : c'est le brut qui la porte, cotisée."""
    ctx = build_test_contexte(
        salaire_base=2200.0,
        type_contrat="CDD",
        date_entree="2025-10-01",
        date_fin_contrat="2026-04-30",
        cumuls={"brut_total": 8800.0},
    )
    ctx.exit_indemnities = {
        "indemnite_preavis": {"montant": 0.0},
        "indemnite_licenciement": {"montant": 0.0},
    }
    res = calculer_salaire_brut(ctx, [], date(2026, 4, 1), date(2026, 4, 30), [])
    gains = _lignes_gain(res)
    iccp = next((v for k, v in gains.items() if "compensatrice de congés" in k), None)
    assert iccp == pytest.approx(1210.0, abs=0.05)


def test_iccp_du_dossier_de_depart_prime_et_entre_dans_le_brut():
    """Le dossier porte sa propre ICCP : c'est elle qui va dans le brut,
    cotisée, et le moteur ne calcule pas le dixième en plus."""
    ctx = build_test_contexte(
        salaire_base=2200.0,
        type_contrat="CDD",
        date_entree="2025-10-01",
        date_fin_contrat="2026-04-30",
        cumuls={"brut_total": 8800.0},
    )
    ctx.exit_indemnities = {"indemnite_conges": {"montant": 900.0}}
    res = calculer_salaire_brut(ctx, [], date(2026, 4, 1), date(2026, 4, 30), [])
    gains = _lignes_gain(res)
    assert gains["Indemnité compensatrice de congés payés"] == 900.0
    assert "Indemnité compensatrice de congés payés (CDD)" not in gains


def test_indemnites_soumises_du_dossier_dans_le_brut_pour_un_cdi():
    """Préavis et congés payés sont des salaires : dans le brut, avant
    cotisations. L'indemnité de licenciement, exonérée, reste hors brut
    (Demory, juillet 2026 : net supérieur au brut quand elles étaient
    ajoutées après les cotisations)."""
    ctx = build_test_contexte(salaire_base=2200.0, type_contrat="CDI", date_entree="2020-01-01")
    ctx.exit_indemnities = {
        "indemnite_preavis": {"montant": 2200.0},
        "indemnite_conges": {"montant": 640.5},
        "indemnite_licenciement": {"montant": 3000.0},
        "indemnite_rupture_conventionnelle": {"montant_negocie": 0.0},
    }
    res = calculer_salaire_brut(ctx, [], date(2026, 4, 1), date(2026, 4, 30), [])
    gains = _lignes_gain(res)
    assert gains["Indemnité compensatrice de préavis"] == 2200.0
    assert gains["Indemnité compensatrice de congés payés"] == 640.5
    assert not any("licenciement" in k.lower() for k in gains)
    assert res["salaire_brut_total"] == pytest.approx(2200.0 + 2200.0 + 640.5, abs=0.05)

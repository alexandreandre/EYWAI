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


# --- Règle légale par période (spec 2026-09-21-indemnite-cp-fin-de-contrat-legale) ---


def _contexte_demory():
    ctx = build_test_contexte(
        salaire_base=1867.06,  # 151,67 h × 12,31 ; les 17,33 h structurelles s'ajoutent à 39 h
        duree_hebdo=39.0,
        type_contrat="CDD",
        date_entree="2026-03-23",
        date_fin_contrat="2026-07-24",
        cumuls={"brut_total": 6197.76, "brut_reference_n_1": 2026.41},
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )
    ctx.cp_fin_de_contrat = {
        "periode_precedente": {"libelle": "2025-2026", "brut": 4171.35, "droits": 3.78, "restants": 2.78},
        "periode_en_cours": {"libelle": "2026-2027", "brut_avant_mois": 2026.41, "droits": 4.16, "restants": 4.16},
    }
    return ctx


def test_indemnite_par_periode_redonne_766_39_sur_demory():
    ctx = _contexte_demory()
    res = calculer_salaire_brut(ctx, [], date(2026, 7, 1), date(2026, 7, 31), [])
    gains = _lignes_gain(res)
    iccp = next(v for k, v in gains.items() if "compensatrice de congés" in k)
    # juillet payé sur 18 jours ouvrés : 1 772,64 ; précarité 797,04 ;
    # période en cours = 2 026,41 + 1 772,64 + 797,04 = 4 596,09 → 459,61 ; précédente 306,78.
    assert gains["Prime de précarité (CDD)"] == pytest.approx(797.04, abs=0.01)
    assert iccp == pytest.approx(766.39, abs=0.01)
    detail = ctx.detail_iccp_fin_contrat
    assert detail["methode"] == "par_periode"
    assert [p["retenu"] for p in detail["periodes"]] == pytest.approx([306.78, 459.61], abs=0.01)
    assert detail["periodes"][1]["brut"] == pytest.approx(4596.09, abs=0.01)
    assert "Total 766,39." in detail["mention"]


def test_sans_compteurs_le_dixieme_global_reste_et_le_detail_le_dit():
    ctx = _contexte_demory()
    del ctx.cp_fin_de_contrat
    res = calculer_salaire_brut(ctx, [], date(2026, 7, 1), date(2026, 7, 31), [])
    gains = _lignes_gain(res)
    iccp = next(v for k, v in gains.items() if "compensatrice de congés" in k)
    assert iccp == pytest.approx(876.74, abs=0.01)
    assert ctx.detail_iccp_fin_contrat["methode"] == "dixieme_global"
    assert "mention" not in ctx.detail_iccp_fin_contrat


def test_sans_jour_restant_pas_de_ligne():
    ctx = _contexte_demory()
    ctx.cp_fin_de_contrat = {
        "periode_precedente": {"libelle": "2025-2026", "brut": 4171.35, "droits": 3.78, "restants": 0.0},
        "periode_en_cours": {"libelle": "2026-2027", "brut_avant_mois": 2026.41, "droits": 4.16, "restants": 0.0},
    }
    res = calculer_salaire_brut(ctx, [], date(2026, 7, 1), date(2026, 7, 31), [])
    assert not any("compensatrice de congés" in k for k in _lignes_gain(res))

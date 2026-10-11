"""Forfait jours : la fin de contrat se paie comme au moteur des heures.

Le moteur du forfait jours n'ajoutait que les lignes du dossier de départ : ni
prime de précarité, ni indemnité compensatrice de congés de fin de CDD, ni règle
par période (enquête H, annexe B). CDD au forfait des 29-30/06/2026, bulletin de
sortie calculé : brut 272,73, sans précarité (27,27 dus) ni indemnité de congés.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

AVRIL = (date(2026, 4, 1), date(2026, 4, 30))


def _cdd_forfait(**kw):
    return build_test_contexte(
        statut="Cadre",
        salaire_base=3000.0,
        type_contrat="CDD",
        date_entree="2025-10-01",
        date_fin_contrat="2026-04-30",
        cumuls={"brut_total": 18000.0},
        specificites_extra={"is_forfait_jour": True},
        **kw,
    )


def _gains(res):
    return {l["libelle"]: l["gain"] for l in res["lignes_composants_brut"] if l.get("gain")}


def test_fin_de_cdd_au_forfait_precarite_et_indemnite_de_conges():
    ctx = _cdd_forfait()
    res = calculer_salaire_brut_forfait(ctx, [], *AVRIL, [])
    gains = _gains(res)
    # Précarité = 10 % de (18 000 + 3 000) ; sans compteurs, l'indemnité de
    # congés est le dixième de tout le contrat, précarité comprise.
    assert gains["Prime de précarité (CDD)"] == pytest.approx(2100.0, abs=0.01)
    assert gains["Indemnité compensatrice de congés payés (CDD)"] == pytest.approx(2310.0, abs=0.01)
    assert res["salaire_brut_total"] == pytest.approx(3000.0 + 2100.0 + 2310.0, abs=0.01)


def test_fin_de_cdd_au_forfait_regle_par_periode_valeur_d_une_journee():
    """Avec les compteurs : par période, le plus favorable du dixième et du
    maintien, un jour valant le salaire / 21,67 (valeur des congés au forfait)."""
    ctx = _cdd_forfait()
    ctx.cp_fin_de_contrat = {
        "periode_en_cours": {"libelle": "2025-2026", "brut_avant_mois": 18000.0, "droits": 17.5, "restants": 5.0},
    }
    res = calculer_salaire_brut_forfait(ctx, [], *AVRIL, [])
    gains = _gains(res)
    # Dixième : 10 % × (18 000 + 3 000 + 2 100) × 5/17,5 = 660,00 ;
    # maintien : 5 × 3 000 / 21,67 = 692,20 → maintien.
    assert gains["Indemnité compensatrice de congés payés (CDD)"] == pytest.approx(692.2, abs=0.01)
    detail = ctx.detail_iccp_fin_contrat
    assert detail["methode"] == "par_periode"
    assert detail["periodes"][0]["dixieme"] == pytest.approx(660.0, abs=0.01)


def test_demission_au_forfait_la_regle_par_periode_remplace_l_estimation_du_dossier():
    ctx = build_test_contexte(
        statut="Cadre", salaire_base=3750.0, type_contrat="CDI", date_entree="2025-08-25",
        specificites_extra={"is_forfait_jour": True},
    )
    ctx.exit_indemnities = {"indemnite_preavis": {"montant": 0.0}, "indemnite_conges": {"montant": 4729.46}}
    ctx.depart_du_mois = True
    ctx.cp_fin_de_contrat = {
        "periode_precedente": {"libelle": "2024-2025", "brut": 3750.0, "droits": 2.08, "restants": 2.08},
        "periode_en_cours": {"libelle": "2025-2026", "brut_avant_mois": 30000.0, "droits": 22.92, "restants": 12.0},
    }
    res = calculer_salaire_brut_forfait(ctx, [], *AVRIL, [])
    lignes = [l for l in res["lignes_composants_brut"] if "compensatrice de congés" in (l.get("libelle") or "")]
    assert len(lignes) == 1
    assert lignes[0]["gain"] == pytest.approx(ctx.detail_iccp_fin_contrat["total"], abs=0.01)
    assert lignes[0]["gain"] != 4729.46


def test_un_mois_ordinaire_au_forfait_ne_change_pas():
    ctx = build_test_contexte(
        statut="Cadre", salaire_base=3750.0, type_contrat="CDI",
        specificites_extra={"is_forfait_jour": True},
    )
    res = calculer_salaire_brut_forfait(ctx, [], *AVRIL, [])
    assert res["salaire_brut_total"] == 3750.0
    assert list(_gains(res)) == ["Salaire de base (forfait jour)"]


# --- Une indemnité de congés saisie au mois l'emporte sur le calcul -----------
# Zone 404, fin de période d'essai de juin 2026 au forfait : la gestionnaire a
# saisi « Indemnités de fin de contrat (CP) » 2 076,60 (bulletin du cabinet) ; le
# moteur ajoutait sa propre indemnité par période (2 536,23) : payée deux fois.

SAISIE_ICCP = {"libelle": "Indemnités de fin de contrat (CP)", "montant": 2076.6, "saisie_id": "s-1"}


def _lignes_conges_de_fin(res):
    return [
        l for l in res["lignes_composants_brut"]
        if "compensatrice de congés" in (l.get("libelle") or "") or "(CP)" in (l.get("libelle") or "")
    ]


def test_au_forfait_l_indemnite_de_conges_saisie_remplace_le_calcul():
    ctx = build_test_contexte(
        statut="Cadre", salaire_base=3000.0, type_contrat="CDI", date_entree="2026-03-02",
        specificites_extra={"is_forfait_jour": True},
    )
    ctx.depart_du_mois = True
    ctx.cp_fin_de_contrat = {
        "periode_en_cours": {"libelle": "2025-2026", "brut_avant_mois": 9000.0, "droits": 10.0, "restants": 10.0},
    }
    res = calculer_salaire_brut_forfait(ctx, [], *AVRIL, [dict(SAISIE_ICCP)])
    assert [(l["libelle"], l["gain"]) for l in _lignes_conges_de_fin(res)] == [
        ("Indemnités de fin de contrat (CP)", 2076.6)
    ]
    assert res["salaire_brut_total"] == pytest.approx(3000.0 + 2076.6, abs=0.01)


def test_au_forfait_une_fin_de_cdd_avec_indemnite_saisie_garde_sa_precarite():
    ctx = _cdd_forfait()
    res = calculer_salaire_brut_forfait(
        ctx, [], *AVRIL, [{"libelle": "Ind.de CP des CDD", "montant": 2300.0, "saisie_id": "s-2"}]
    )
    gains = _gains(res)
    assert gains["Prime de précarité (CDD)"] == pytest.approx(2100.0, abs=0.01)
    assert "Indemnité compensatrice de congés payés (CDD)" not in gains
    assert gains["Ind.de CP des CDD"] == 2300.0


def test_aux_heures_l_indemnite_de_conges_saisie_remplace_aussi_le_calcul():
    from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

    ctx = build_test_contexte(salaire_base=2200.0, type_contrat="CDI", date_entree="2020-01-01")
    ctx.exit_indemnities = {"indemnite_preavis": {"montant": 0.0}, "indemnite_conges": {"montant": 999.0}}
    ctx.depart_du_mois = True
    ctx.cp_fin_de_contrat = {
        "periode_en_cours": {"libelle": "2025-2026", "brut_avant_mois": 22000.0, "droits": 25.0, "restants": 20.0},
    }
    saisie = {"libelle": "Indemnité compensatrice de congés payés", "montant": 1800.0, "saisie_id": "s-3"}
    res = calculer_salaire_brut(ctx, [], *AVRIL, [saisie])
    lignes = [(l["libelle"], l["gain"]) for l in res["lignes_composants_brut"] if "compensatrice de congés" in (l.get("libelle") or "")]
    assert lignes == [("Indemnité compensatrice de congés payés", 1800.0)]


def test_une_absence_de_conges_saisie_n_est_pas_une_indemnite_de_fin_de_contrat():
    from app.modules.payroll.engine.calcul_brut import iccp_saisie_au_mois

    assert not iccp_saisie_au_mois([{"libelle": "Abs. Congés s.solde", "montant": -92.31}])
    assert not iccp_saisie_au_mois([{"libelle": "Indemnité de fin de contrat", "montant": 500.0}])
    assert iccp_saisie_au_mois([{"libelle": "Indemnités de fin de contrat (CP, rupture)", "montant": 4281.5}])
    assert iccp_saisie_au_mois([{"libelle": "Ind.de CP des CDD", "montant": 195.97}])

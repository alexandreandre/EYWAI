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

"""Minimums de branche de sortie : plasturgie et métallurgie (R-346, R-347)."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine import calcul_indemnites_sortie as sortie
from app.modules.payroll.engine.indemnites_conventionnelles_branches import (
    indemnite_metallurgie_depart_retraite,
    indemnite_plasturgie_depart_retraite,
    indemnite_plasturgie_licenciement,
)

pytestmark = pytest.mark.unit


def _licenciement(coefficient, mois, statut="Non-Cadre", salaire=1000.0):
    return indemnite_plasturgie_licenciement(
        coefficient=coefficient, statut=statut, mois_d_anciennete=mois, salaire_reference=salaire
    )


def test_collaborateur_plasturgie_le_barème_legal_et_les_deux_reserves():
    r = _licenciement(740.0, 15 * 12)
    assert r["montant"] == round(1000 * (10 / 4 + 5 / 3), 2)
    assert any("dernier" in a for a in r["alertes"]) and any("Seine" in a for a in r["alertes"])


def test_cadre_plasturgie_moins_de_trois_ans_un_quart():
    assert _licenciement(900.0, 24, "Cadre")["montant"] == 500.0


def test_cadre_plasturgie_tranches_depuis_l_entree():
    # 15 ans : 8 × 3/10 + 5 × 4/10 + 2 × 5/10 = 2,4 + 2 + 1 = 5,4 mois.
    assert _licenciement(900.0, 15 * 12, "Cadre")["mois_de_salaire"] == 5.4


def test_cadre_plasturgie_plafond_de_quinze_mois():
    assert _licenciement(940.0, 40 * 12, "Cadre")["mois_de_salaire"] == 15.0


def test_sous_huit_mois_rien():
    assert _licenciement(740.0, 7) is None


def test_sans_coefficient_ni_statut_c_est_dit():
    r = _licenciement(None, 60, statut="")
    assert r["montant"] is None and "coefficient" in r["alertes"][0]


def test_sans_coefficient_le_statut_non_cadre_donne_le_bareme_legal():
    assert _licenciement(None, 60)["montant"] == 1250.0


def test_depart_collaborateur_moitie_dans_la_limite_de_trente_ans():
    # 30 ans : 55/12 de mois, soit la moitié de 2,5 + 20/3 mois.
    r = indemnite_plasturgie_depart_retraite(
        coefficient=740.0, statut="Non-Cadre", mois_d_anciennete=30 * 12, salaire_reference=2766.54
    )
    assert r["montant"] == 12679.98
    plus_long = indemnite_plasturgie_depart_retraite(
        coefficient=740.0, statut="Non-Cadre", mois_d_anciennete=38 * 12, salaire_reference=2766.54
    )
    assert plus_long["montant"] == 12679.98


def test_depart_cadre_seuil_tranches_et_plafond():
    depart = lambda annees: indemnite_plasturgie_depart_retraite(  # noqa: E731
        coefficient=900.0, statut="Cadre", mois_d_anciennete=annees * 12, salaire_reference=1000.0
    )
    assert depart(4) is None
    assert depart(5)["mois_de_salaire"] == 0.75
    assert depart(15)["mois_de_salaire"] == round(8 * 0.15 + 5 * 0.2 + 2 * 0.25, 4)
    assert depart(40)["mois_de_salaire"] == 7.5


def test_depart_cadre_au_dela_de_940_c_est_dit():
    r = indemnite_plasturgie_depart_retraite(
        coefficient=950.0, statut="Cadre", mois_d_anciennete=240, salaire_reference=1000.0
    )
    assert r["montant"] is None and "940" in r["alertes"][0]


@pytest.mark.parametrize(
    "annees,mois", [(1, None), (2, 0.5), (5, 1.0), (10, 2.0), (20, 3.0), (30, 4.0), (35, 5.0), (40, 6.0)]
)
def test_depart_metallurgie_bareme(annees, mois):
    r = indemnite_metallurgie_depart_retraite(mois_d_anciennete=annees * 12, salaire_reference=1000.0)
    assert (r or {}).get("mois_de_salaire") == mois


def _bloc():
    return {"montant": 1000.0, "alertes": [], "calcul": "légal", "base_calcul": "Légale"}


def test_le_minimum_de_branche_plus_eleve_est_verse_et_le_dit():
    r = sortie._retenir_minimum_de_branche(
        _bloc(),
        None,
        {"montant": 1500.0, "calcul": "Convention", "alertes": ["a"]},
        libelle="L",
        description="D",
    )
    assert r["montant"] == 1500.0 and r["base_calcul"] == "Conventionnelle"
    assert r["calcul"].startswith("Convention") and "saisie" not in r["calcul"]
    assert r["alertes"] == ["a"]


def test_egal_au_legal_le_legal_reste_sans_dire_saisie():
    r = sortie._retenir_minimum_de_branche(
        _bloc(), None, {"montant": 1000.0, "calcul": "C", "alertes": []}, libelle="L", description="D"
    )
    assert r["montant"] == 1000.0 and r["base_calcul"] == "Légale"
    assert "calculée par Martine" in r["calcul"]


def test_un_montant_saisi_plus_haut_l_emporte():
    r = sortie._retenir_minimum_de_branche(
        _bloc(), 2000.0, {"montant": 1500.0, "calcul": "C", "alertes": []}, libelle="L", description="D"
    )
    assert r["montant"] == 2000.0


def test_coefficient_inconnu_garde_le_legal_et_l_alerte():
    r = sortie._retenir_minimum_de_branche(
        _bloc(), None, {"montant": None, "calcul": "", "alertes": ["manque"]}, libelle="L", description="D"
    )
    assert r["montant"] == 1000.0 and "manque" in r["alertes"]


def test_le_plancher_lit_la_convention_de_la_fiche():
    employe = {
        "classification_conventionnelle": {"idcc": "292", "coefficient": 900},
        "statut": "Cadre",
    }
    r = sortie._plancher_conventionnel(
        employe,
        None,
        mois_d_anciennete=15 * 12,
        salaire_reference=1000.0,
        a_la_date=date(2026, 11, 8),
        nature="depart_retraite",
    )
    assert r["mois_de_salaire"] == round(8 * 0.15 + 5 * 0.2 + 2 * 0.25, 4)


def test_mise_a_la_retraite_metallurgie_renvoie_au_code_du_travail():
    employe = {"classification_conventionnelle": {"idcc": "3248", "groupe_emploi": "F"}}
    assert (
        sortie._plancher_conventionnel(
            employe,
            None,
            mois_d_anciennete=240,
            salaire_reference=1000.0,
            a_la_date=date(2026, 11, 8),
            nature="mise_retraite",
        )
        is None
    )

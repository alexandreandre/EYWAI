"""Congés acquis pendant un préavis dont l'employeur dispense le salarié.

Code du travail, art. L1234-5 (Légifrance, version en vigueur depuis le
01/05/2008, ouvert le 11/10/2026) : « L'inexécution du préavis, notamment en
cas de dispense par l'employeur, n'entraîne aucune diminution des salaires et
avantages que le salarié aurait perçus s'il avait accompli son travail jusqu'à
l'expiration du préavis, indemnité de congés payés comprise. »

Code du travail, art. L3141-24, I (version en vigueur depuis le 24/04/2024,
ouvert le 11/10/2026) : l'indemnité de congé est « égale au dixième de la
rémunération brute totale perçue par le salarié au cours de la période de
référence ».

Martine arrêtait les compteurs de congés au dernier jour travaillé et
calculait le dixième sans l'indemnité compensatrice de préavis : un salarié
dispensé de deux mois de préavis perdait cinq jours ouvrables de congés et le
dixième de deux mois de salaire.

Règle appliquée : les jours que le salarié aurait acquis jusqu'à la fin
théorique du préavis (au rythme de la société, 2,5 jours ouvrables par mois de
30 jours par défaut) s'ajoutent aux droits et aux jours restants de la période
où ils tombent, et l'indemnité compensatrice de préavis entre dans la
rémunération brute de cette période. Seule la dispense par l'employeur est
concernée : un préavis exécuté est payé et acquiert les congés au mois le mois,
une dispense demandée par le salarié ne paie rien.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_indemnites_sortie import calculer_indemnites_sortie
from app.modules.payroll.engine.iccp_fin_contrat import PeriodeConges
from app.modules.payroll.engine.preavis import (
    CongesDuPreavis,
    ajouter_les_conges_du_preavis,
    conges_du_preavis_non_execute,
)
from tests.unit.base_en_memoire import BaseEnMemoire
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit


def test_deux_mois_de_preavis_dispense_acquierent_cinq_jours():
    parts = conges_du_preavis_non_execute(
        dernier_jour_travaille=date(2026, 9, 30),
        fin_du_preavis=date(2026, 11, 29),
        indemnite=6000.0,
        acquisition_par_mois=2.5,
        mois_debut_periode=6,
    )
    assert parts == [CongesDuPreavis(libelle=None, jours=5.0, brut=6000.0)]


def test_un_preavis_qui_passe_le_31_mai_se_partage_entre_deux_periodes():
    parts = conges_du_preavis_non_execute(
        dernier_jour_travaille=date(2027, 4, 30),
        fin_du_preavis=date(2027, 6, 29),
        indemnite=6000.0,
        acquisition_par_mois=2.5,
        mois_debut_periode=6,
    )
    assert parts == [
        CongesDuPreavis(libelle=None, jours=2.58, brut=3100.0),
        CongesDuPreavis(libelle="2027-2028", jours=2.42, brut=2900.0),
    ]


def test_les_jours_et_l_indemnite_s_ajoutent_a_leur_periode():
    periodes = [
        PeriodeConges("2025-2026", 26400.0, 30.0, 5.0),
        PeriodeConges("2026-2027", 9000.0, 10.0, 10.0),
    ]
    resultat = ajouter_les_conges_du_preavis(
        periodes,
        [CongesDuPreavis(None, 2.58, 3100.0), CongesDuPreavis("2027-2028", 2.42, 2900.0)],
    )
    assert resultat == [
        PeriodeConges("2025-2026", 26400.0, 30.0, 5.0),
        PeriodeConges("2026-2027", 12100.0, 12.58, 12.58),
        PeriodeConges("2027-2028", 2900.0, 2.42, 2.42),
    ]


def _contexte_de_demission(preavis: dict):
    ctx = build_test_contexte(salaire_base=2200.0, type_contrat="CDI", date_entree="2020-01-01")
    ctx.exit_indemnities = {"indemnite_preavis": preavis, "indemnite_conges": {"montant": 0.0}}
    ctx.depart_du_mois = True
    ctx.cp_fin_de_contrat = {
        "periode_precedente": {"libelle": "2024-2025", "brut": 26400.0, "droits": 30.0, "restants": 5.0},
        "periode_en_cours": {"libelle": "2025-2026", "brut_avant_mois": 22000.0, "droits": 25.0, "restants": 20.0},
    }
    return ctx


def test_le_bulletin_indemnise_les_conges_du_preavis_dispense_par_l_employeur():
    preavis = {
        "montant": 4400.0,
        "type": "paid",
        "jours_restants": 60,
        "conges_du_preavis": [{"libelle": None, "jours": 5.0, "brut": 4400.0}],
    }
    ctx = _contexte_de_demission(preavis)
    res = calculer_salaire_brut(ctx, [], date(2026, 4, 1), date(2026, 4, 30), [])

    (en_cours,) = [p for p in ctx.detail_iccp_fin_contrat["periodes"] if p["libelle"] == "2025-2026"]
    assert en_cours["droits"] == 30.0
    assert en_cours["restants"] == 25.0
    # Le brut du mois de sortie et l'indemnité compensatrice de préavis.
    assert en_cours["brut"] == pytest.approx(22000.0 + 2200.0 + 4400.0, abs=0.01)
    lignes_preavis = [
        l for l in res["lignes_composants_brut"] if l.get("libelle") == "Indemnité compensatrice de préavis"
    ]
    assert [l["gain"] for l in lignes_preavis] == [4400.0]


def test_un_preavis_execute_ne_change_pas_les_conges_de_sortie():
    ctx = _contexte_de_demission({"montant": 0.0, "type": "executed", "jours_preavis": 60})
    calculer_salaire_brut(ctx, [], date(2026, 4, 1), date(2026, 4, 30), [])

    (en_cours,) = [p for p in ctx.detail_iccp_fin_contrat["periodes"] if p["libelle"] == "2025-2026"]
    assert en_cours["droits"] == 25.0
    assert en_cours["restants"] == 20.0


_PERIODES = {
    "periode_precedente": {"libelle": "2025-2026", "brut": 30000.0, "droits": 30.0, "restants": 6.0},
    "periode_en_cours": {"libelle": "2026-2027", "brut_avant_mois": 9000.0, "droits": 10.0, "restants": 10.0},
}


class _Politique:
    cp_acquisition_days_per_month = 2.5
    cp_reference_period_start_month = 6


@patch("app.modules.payroll.engine.calcul_indemnites_sortie._conges_par_periode_a_la_sortie", return_value=_PERIODES)
@patch(
    "app.modules.absences.infrastructure.leave_settings_repository.get_leave_policy",
    return_value=_Politique(),
)
def test_le_dossier_compte_les_conges_du_preavis_dans_son_estimation(_politique, _periodes):
    salarie = {
        "id": "emp-1",
        "company_id": "co-1",
        "hire_date": "2020-01-01",
        "contract_type": "CDI",
        "salaire_de_base": {"valeur": 3000.0},
        "duree_hebdomadaire": 35,
        "baremes": {"pss": {"annuel": 48060.0}},
    }
    depart = {
        "id": "exit-1",
        "exit_type": "licenciement",
        "exit_request_date": "2026-09-01",
        "last_working_day": "2026-09-30",
        "notice_period_days": 60,
        "notice_end_date": "2026-11-29",
        "notice_indemnity_type": "paid",
    }
    dossier = calculer_indemnites_sortie(salarie, depart, BaseEnMemoire({}))

    preavis = dossier["indemnite_preavis"]
    assert preavis["montant"] == 6000.0
    assert preavis["conges_du_preavis"] == [{"libelle": None, "jours": 5.0, "brut": 6000.0}]
    assert "5 jours" in preavis["calcul"]
    periodes = {p["libelle"]: p for p in dossier["indemnite_conges"]["details"]["periodes"]}
    assert periodes["2026-2027"]["droits"] == 15.0
    assert periodes["2026-2027"]["restants"] == 15.0
    assert periodes["2026-2027"]["brut"] == pytest.approx(9000.0 + 3000.0 + 6000.0, abs=0.01)

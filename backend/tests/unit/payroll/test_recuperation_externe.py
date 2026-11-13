"""Le type Repos proposé à la RH n'invente ni retenue ni congé payé.

Le compteur et les heures restant à payer sont décidés à l'extérieur. On
vérifie aussi le cas témoin : une vraie absence non rémunérée reste retenue.
"""
from datetime import date

import pytest

from app.modules.payroll.application.analyzer import analyser_horaires_du_mois
from app.modules.payroll.documents.payslip_run_heures import jour_du_calendrier_final
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.schedules.domain.ecart_rules import is_day_ready_for_payroll
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _planning(type_jour):
    prevu = [
        {"annee": 2026, "mois": 11, "jour": j, "type": "travail", "heures_prevues": 7.0}
        for j in range(2, 7)
    ]
    prevu[-1].update(type=type_jour, heures_prevues=0.0 if type_jour == "repos" else 7.0)
    reel = [
        {"annee": 2026, "mois": 11, "jour": j, "type": "travail", "heures_faites": 0.0 if j == 6 else 7.0}
        for j in range(2, 7)
    ]
    return prevu, reel


def _brut(type_jour, *, primes=None):
    prevu, reel = _planning(type_jour)
    evenements = analyser_horaires_du_mois(prevu, reel, 35.0, 2026, 11, 'Salarié test')
    calendrier = [
        {**e, "date_complete": date(2026, 11, e["jour"]).isoformat()}
        for e in evenements
    ]
    contexte = build_test_contexte(salaire_base=2500.0, duree_hebdo=35.0)
    resultat = calculer_salaire_brut(
        contexte, calendrier, date(2026, 11, 1), date(2026, 11, 30),
        primes_saisies=primes or [],
    )
    return evenements, resultat


def test_le_repos_a_zero_ne_devient_pas_une_absence_ni_des_cp():
    prevu, reel = _planning("repos")
    assert is_day_ready_for_payroll(prevu[-1], reel[-1])
    evenements, resultat = _brut("repos")
    jour_analyse = next((e for e in evenements if e['jour'] == 6), None)
    assert jour_du_calendrier_final(prevu[-1], jour_analyse, 6)["type"] == "repos"
    assert not any(e["type"].startswith(("absence", "conge", "travail_hs")) for e in evenements)
    assert resultat["salaire_brut_total"] == 2500.0
    assert resultat["heures_absence_non_payees"] == 0.0


def test_une_vraie_absence_non_remuneree_reste_deduite():
    evenements, resultat = _brut("absence_non_remuneree")
    assert any(e["type"] == "absence_non_remuneree" for e in evenements)
    assert resultat["salaire_brut_total"] < 2500.0
    assert resultat["heures_absence_non_payees"] == 7.0


def test_la_periode_du_rappel_est_conservee_dans_la_ligne_du_bulletin():
    libelle = "Rappel de maintien de salaire du 01/10/2026 au 05/10/2026"
    _, resultat = _brut("repos", primes=[{
        "prime_id": "rappel_maintien_salaire", "libelle": libelle,
        "montant": 100.0, "soumise_a_cotisations": True, "soumise_a_impot": True,
    }])
    ligne = next(l for l in resultat["lignes_composants_brut"] if l.get("libelle") == libelle)
    assert ligne["gain"] == 100.0
    assert resultat["salaire_brut_total"] == 2600.0

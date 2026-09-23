"""Une ligne de prime garde l'identifiant de la saisie qui l'a produite.

Sans ce lien, corriger ou retirer une prime depuis le bulletin ne saurait pas
quelle variable du mois modifier (spec 2026-09-23).
"""

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.lien_saisie import lier_a_la_saisie
from tests.unit.payroll.helpers import _weekday_calendrier, build_test_contexte

pytestmark = pytest.mark.unit


def test_le_lien_est_recopie_quand_la_source_en_porte_un():
    assert lier_a_la_saisie({"libelle": "Prime"}, {"saisie_id": "s-1"}) == {
        "libelle": "Prime",
        "saisie_id": "s-1",
    }


def test_sans_lien_la_ligne_est_inchangee():
    assert lier_a_la_saisie({"libelle": "Prime"}, {"libelle": "Prime"}) == {
        "libelle": "Prime"
    }


def test_une_prime_saisie_imprime_son_lien_dans_le_brut():
    contexte = build_test_contexte()
    contexte.year = 2026

    resultat = calculer_salaire_brut(
        contexte,
        calendrier_saisie=_weekday_calendrier(2026, 4),
        date_debut_periode=date(2026, 4, 1),
        date_fin_periode=date(2026, 4, 30),
        primes_saisies=[
            {"libelle": "Prime exceptionnelle", "montant": 100.0, "prime_id": "x", "saisie_id": "s-1"},
            {"libelle": "Prime sans saisie", "montant": 50.0, "prime_id": "y"},
        ],
    )

    lignes = {ligne["libelle"]: ligne for ligne in resultat["lignes_composants_brut"]}
    assert lignes["Prime exceptionnelle"]["saisie_id"] == "s-1"
    assert "saisie_id" not in lignes["Prime sans saisie"]

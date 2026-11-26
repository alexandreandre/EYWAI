"""Indemnité d'activité partielle : la prime d'ancienneté entre dans son assiette (R5122-18).

R5122-18 (code.travail.gouv.fr, lu le 26/11/2026) : l'indemnité vaut 60 % de la
« rémunération brute servant d'assiette de l'indemnité de congés payés telle que prévue
au II de l'article L. 3141-24 », ramenée à l'heure. Ce II est le maintien du salaire que
le salarié aurait perçu s'il avait travaillé : la prime d'ancienneté en fait partie.
L'indemnité se calcule donc sur salaire horaire × (1 + prime ÷ salaire), avec le plancher,
le plafond, et jamais plus que cette assiette. La retenue des heures chômées reste au
salaire horaire : la prime du mois en est déjà diminuée.

Calcul complet aux deux moteurs (heures et forfait jours), hors ligne.
"""

from __future__ import annotations

import pytest

from app.modules.activite_partielle.domain.calcul import (
    CLE_CALCUL_INDEMNITE,
    assiette_horaire_avec_prime,
    calculer,
    indemnite_par_heure,
)
from app.modules.payroll.engine import calcul_brut, calcul_brut_forfait
from app.modules.payroll.engine.activite_partielle import indemnite_avec_la_prime
from tests.unit.payroll.test_activite_partielle_deux_moteurs import (
    MOTEURS,
    RETENUE,
    _bulletin,
    _hors_ligne,  # noqa: F401  (fixture : aucun appel réseau)
)

pytestmark = pytest.mark.unit

TAUX = round(2500 / 151.67, 4)
CALCUL = {
    "heures": 14.0,
    "taux_horaire": TAUX,
    "salaire_mensuel": 2500.0,
    "taux_indemnite": 60.0,
    "plancher": 9.74,
    "plafond": 33.24,
}
#: 14 h au taux du salaire seul : 14 × 60 % × 16,4832 = 138,46 €.
SANS_PRIME = round(14 * round(TAUX * 0.6, 4), 2)


def _indemnite(montant=SANS_PRIME, calcul=CALCUL):
    ligne = {
        "prime_id": "Indemnité_activité_partielle",
        "libelle": "Indemnité activité partielle",
        "montant": montant,
        "quantity": 14.0,
        "soumise_a_cotisations": False,
        "soumise_a_impot": True,
    }
    if calcul is not None:
        ligne[CLE_CALCUL_INDEMNITE] = dict(calcul)
    return ligne


# --- Domaine ---------------------------------------------------------------


def test_l_assiette_porte_la_prime_au_prorata_du_salaire():
    assert assiette_horaire_avec_prime(16.4832, 2500.0, 100.0) == round(16.4832 * 1.04, 4)
    assert assiette_horaire_avec_prime(16.4832, 2500.0, 0.0) == 16.4832
    assert assiette_horaire_avec_prime(16.4832, None, 100.0) == 16.4832


def test_plancher_plafond_et_jamais_plus_que_l_assiette():
    assert indemnite_par_heure(17.14, taux_indemnite=60, plancher=9.74, plafond=33.24)[0] == 10.284
    assert indemnite_par_heure(12.0, taux_indemnite=60, plancher=9.74, plafond=33.24)[0] == 9.74
    assert indemnite_par_heure(70.0, taux_indemnite=60, plancher=9.74, plafond=33.24)[0] == 33.24
    # Accord à 100 % : l'indemnité s'arrête à l'assiette.
    assert indemnite_par_heure(17.14, taux_indemnite=100, plancher=9.74, plafond=33.24)[0] == 17.14


def test_la_retenue_reste_au_salaire_horaire_l_indemnite_suit_l_assiette():
    c = calculer(14.0, 16.4832, assiette_horaire=17.1425)
    assert c.retenue == round(14 * 16.4832, 2)
    assert c.indemnite_horaire == round(17.1425 * 0.6, 4)
    sans = calculer(14.0, 16.4832)
    assert sans.indemnite_horaire == round(16.4832 * 0.6, 4)


def test_une_indemnite_saisie_a_la_main_ne_bouge_pas():
    ligne = {"montant": 120.0}
    indemnite_avec_la_prime(ligne, None, 100.0)
    assert ligne == {"montant": 120.0}


def test_sans_prime_rien_ne_change():
    ligne = {"montant": SANS_PRIME}
    indemnite_avec_la_prime(ligne, CALCUL, 0.0)
    assert ligne == {"montant": SANS_PRIME}


# --- Calcul complet, heures et forfait jours --------------------------------


@pytest.fixture
def prime_de_100(monkeypatch):
    """Une prime d'ancienneté de 100 € de plein mois, connue au calcul du brut."""

    def fausse_prime(contexte, **_k):
        contexte.prime_anciennete_plein_mois = 100.0
        return None

    monkeypatch.setattr(calcul_brut, "_calculer_prime_anciennete", fausse_prime)
    monkeypatch.setattr(calcul_brut_forfait, "_calculer_prime_anciennete", fausse_prime)


def _revenu(b: dict) -> dict:
    (ligne,) = b["revenus_hors_brut_imposables"]
    return ligne


@pytest.mark.parametrize("moteur", sorted(MOTEURS))
def test_l_indemnite_du_calendrier_porte_la_prime(tmp_path, moteur, prime_de_100):
    b = _bulletin(tmp_path, moteur, [RETENUE, _indemnite()])
    horaire = round(round(TAUX * 1.04, 4) * 0.6, 4)
    assert _revenu(b)["montant"] == round(14 * horaire, 2) == 144.0
    assert _revenu(b)["quantite"] == 14.0
    # La retenue des heures chômées ne bouge pas.
    retenue = [l for l in b["calcul_du_brut"] if l.get("libelle") == RETENUE["libelle"]]
    assert retenue[0]["gain"] == RETENUE["montant"]


@pytest.mark.parametrize("moteur", sorted(MOTEURS))
def test_l_indemnite_saisie_a_la_main_reste_telle_quelle(tmp_path, moteur, prime_de_100):
    b = _bulletin(tmp_path, moteur, [RETENUE, _indemnite(montant=120.0, calcul=None)])
    assert _revenu(b)["montant"] == 120.0


@pytest.mark.parametrize("moteur", sorted(MOTEURS))
def test_sans_prime_d_anciennete_l_indemnite_du_calendrier_ne_bouge_pas(tmp_path, moteur):
    b = _bulletin(tmp_path, moteur, [RETENUE, _indemnite()])
    assert _revenu(b)["montant"] == SANS_PRIME


def test_la_saisie_du_bulletin_garde_le_calcul_de_la_ligne_du_calendrier():
    from app.modules.payroll.documents.saisies_du_bulletin import entree_de_prime

    ligne = {"name": "Indemnité activité partielle", "amount": SANS_PRIME, "payroll_quantity": 14.0,
             "is_socially_taxed": False, CLE_CALCUL_INDEMNITE: CALCUL}
    assert entree_de_prime(ligne)[CLE_CALCUL_INDEMNITE] == CALCUL
    a_la_main = {"name": "Indemnité activité partielle", "amount": 120.0, "id": "s1"}
    assert CLE_CALCUL_INDEMNITE not in entree_de_prime(a_la_main)

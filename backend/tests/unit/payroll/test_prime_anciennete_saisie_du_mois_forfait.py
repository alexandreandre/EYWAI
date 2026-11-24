"""Forfait jours : la prime d'ancienneté du mois saisie remplace le calcul conventionnel.

Même règle que le générateur des heures (test_prime_anciennete_saisie_du_mois) :
le bulletin forfait ajoutait la prime calculée à la prime saisie (reprise d'un
bulletin réel), soit deux primes d'ancienneté. Le défaut restait caché tant que
les jours travaillés au forfait valaient 0 sur une période à cheval (prime
calculée nulle) ; filet du 24/11, deux bulletins forfait de février et juin.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine import calcul_brut_forfait

from .helpers import _weekday_calendrier, build_test_contexte

pytestmark = pytest.mark.unit

PRIME_CONVENTIONNELLE = {
    "libelle": "Prime d'ancienneté",
    "quantite": None,
    "taux": None,
    "gain": 80.0,
    "perte": None,
}


@pytest.fixture
def calcul_conventionnel(monkeypatch):
    monkeypatch.setattr(
        calcul_brut_forfait,
        "_calculer_prime_anciennete",
        lambda *_a, **_k: dict(PRIME_CONVENTIONNELLE),
    )


def _brut(primes):
    ctx = build_test_contexte(salaire_base=3000.0)
    ctx.year = 2026
    resultat = calcul_brut_forfait.calculer_salaire_brut_forfait(
        ctx,
        calendrier_saisie=_weekday_calendrier(2026, 2),
        date_debut_periode=date(2026, 2, 1),
        date_fin_periode=date(2026, 2, 28),
        primes_saisies=primes,
    )
    gains = {
        l.get("libelle"): l.get("gain")
        for l in resultat["lignes_composants_brut"]
        if "anciennet" in str(l.get("libelle") or "").lower()
    }
    alertes = [a for a in ctx.alertes_baremes if a.get("code") == "prime_anciennete_remplacee"]
    return gains, alertes


def test_la_prime_du_mois_saisie_remplace_le_calcul_et_le_bulletin_le_dit(calcul_conventionnel):
    gains, alertes = _brut(
        [{"prime_id": "prime_anciennete", "libelle": "Prime ancienneté", "montant": 75.0}]
    )

    assert "Prime d'ancienneté" not in gains
    assert gains["Prime ancienneté"] == 75.0
    (alerte,) = alertes
    assert "80,00" in alerte["message"] and "Prime ancienneté" in alerte["message"]


def test_une_regularisation_s_ajoute_a_la_prime_du_mois(calcul_conventionnel):
    gains, alertes = _brut(
        [{"prime_id": "regul", "libelle": "Régul prime ancienneté 01/26", "montant": 30.0}]
    )

    assert gains["Prime d'ancienneté"] == 80.0
    assert gains["Régul prime ancienneté 01/26"] == 30.0
    assert alertes == []


def test_sans_saisie_la_prime_calculee_reste(calcul_conventionnel):
    gains, alertes = _brut([])

    assert gains == {"Prime d'ancienneté": 80.0}
    assert alertes == []

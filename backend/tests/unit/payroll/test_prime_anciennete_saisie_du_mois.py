"""Une régularisation d'ancienneté n'écarte pas la prime conventionnelle du mois. [G4]

Toute saisie dont le nom contenait « anciennet » écartait le calcul
conventionnel : une « Régul prime ancienneté 01/26 » saisie seule dans un mois
faisait disparaître la prime du mois, sans un mot.

Désormais seule une saisie qui EST la prime du mois (montant positif, ni
régularisation ni rappel) remplace le calcul conventionnel, et le bulletin dit
alors qu'il l'a écarté ; une régularisation s'ajoute au calcul.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine import calcul_brut

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
        calcul_brut, "_calculer_prime_anciennete", lambda *_a, **_k: dict(PRIME_CONVENTIONNELLE)
    )


def _brut(primes):
    ctx = build_test_contexte(salaire_base=2000.0)
    ctx.year = 2026
    resultat = calcul_brut.calculer_salaire_brut(
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


@pytest.mark.parametrize(
    "libelle",
    ["Régul prime ancienneté 01/26", "Rappel prime d'ancienneté", "Regularisation anciennete"],
)
def test_une_regularisation_s_ajoute_a_la_prime_du_mois(calcul_conventionnel, libelle):
    gains, alertes = _brut([{"prime_id": "regul", "libelle": libelle, "montant": 30.0}])

    assert gains["Prime d'ancienneté"] == 80.0
    assert gains[libelle] == 30.0
    assert alertes == []


def test_une_reprise_negative_n_ecarte_pas_la_prime(calcul_conventionnel):
    gains, _ = _brut([{"prime_id": "prime_anciennete", "libelle": "Prime ancienneté", "montant": -20.0}])

    assert gains["Prime d'ancienneté"] == 80.0


def test_la_prime_du_mois_saisie_remplace_le_calcul_et_le_bulletin_le_dit(calcul_conventionnel):
    gains, alertes = _brut(
        [{"prime_id": "prime_anciennete", "libelle": "Prime ancienneté", "montant": 75.0}]
    )

    assert "Prime d'ancienneté" not in gains
    assert gains["Prime ancienneté"] == 75.0
    (alerte,) = alertes
    assert "80,00" in alerte["message"] and "Prime ancienneté" in alerte["message"]


def test_sans_calcul_conventionnel_pas_d_alerte(monkeypatch):
    monkeypatch.setattr(calcul_brut, "_calculer_prime_anciennete", lambda *_a, **_k: None)
    gains, alertes = _brut(
        [{"prime_id": "prime_anciennete", "libelle": "Prime ancienneté", "montant": 75.0}]
    )

    assert gains == {"Prime ancienneté": 75.0}
    assert alertes == []

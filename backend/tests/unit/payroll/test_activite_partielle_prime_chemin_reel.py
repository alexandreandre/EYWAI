"""Activité partielle et prime d'ancienneté, sur le vrai calcul de la prime (aux deux générateurs).

La prime d'un mois travaillé (plein mois × quotité) entre dans l'assiette de l'indemnité
(R5122-18) seulement quand la prime baisse avec les heures chômées (prorata actif,
métallurgie). Sans prorata, la prime est versée en entier : la compter aussi dans
l'indemnité la paierait deux fois (relecture du 26/11 : 59,81 € de trop pour 216 € de
prime et 70 h chômées). Une prime saisie qui remplace le calcul n'entre pas dans
l'assiette, et le bulletin le dit.

Pour chaque cas : prime du brut + part de la prime dans l'indemnité ≤ prime d'un mois
travaillé × (part travaillée + 60 % de la part chômée).
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.activite_partielle import indemnite_avec_la_prime
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait
from tests.unit.payroll.test_prime_anciennete_temps_paye import (
    FERIE,
    LIBELLE_AP,
    NOVEMBRE,
    PERIODE_19_JOURS,
    PLEIN_FORFAIT,
    PLEIN_HEURES,
    _calendrier_forfait,
    _calendrier_heures,
    _contexte,
    _prime,
)

pytestmark = pytest.mark.unit

SALAIRE = 2400.0


def _calcul(heures: float, taux: float) -> dict:
    return {"heures": heures, "taux_horaire": taux, "salaire_mensuel": SALAIRE,
            "taux_indemnite": 60.0, "plancher": 9.74, "plafond": 33.24}


def _indemnite(calcul: dict, prime) -> float:
    ligne = {"montant": 0.0}
    indemnite_avec_la_prime(ligne, calcul, prime)
    if ligne["montant"] == 0.0:  # sans prime : le calcul de l'écran, inchangé
        heures, taux = calcul["heures"], calcul["taux_horaire"]
        return round(heures * round(max(taux * 0.6, 9.74), 4), 2)
    return ligne["montant"]


def _retenue_ap(heures: float, taux: float) -> list[dict]:
    return [{"prime_id": "heures_chomees", "libelle": LIBELLE_AP, "montant": -round(heures * taux, 2),
             "quantite": heures}]


def _sans_prorata(ctx):
    regles = ctx.baremes["conventions_collectives"]["idcc_3248"]["prime_anciennete"]
    regles["prorata"] = {"enabled": False, "mode": "none"}
    return ctx


def test_heures_28_h_prorata_actif():
    ctx = _contexte(duree=28)
    heures, contrat = 28.0, 121.33
    taux = round(SALAIRE / (28 * 52 / 12), 4)
    brut = calculer_salaire_brut(ctx, _calendrier_heures(*NOVEMBRE), *NOVEMBRE, _retenue_ap(heures, taux),
                                 jours_maintien=set())
    mois_travaille = round(PLEIN_HEURES * 0.8, 2)
    assert ctx.prime_anciennete_plein_mois == mois_travaille == 67.28
    prime_brut = _prime(brut)
    assert prime_brut == round(PLEIN_HEURES * round(0.8 * (contrat - heures) / contrat, 6), 2)
    part_dans_l_indemnite = _indemnite(_calcul(heures, taux), ctx.prime_anciennete_plein_mois) - _indemnite(
        _calcul(heures, taux), None)
    plafond = mois_travaille * ((contrat - heures) / contrat + 0.6 * heures / contrat)
    assert prime_brut + part_dans_l_indemnite <= round(plafond, 2) + 0.02
    assert part_dans_l_indemnite > 0


def test_heures_sans_prorata_la_prime_n_entre_pas_dans_l_indemnite():
    ctx = _sans_prorata(_contexte())
    taux = round(SALAIRE / 151.67, 4)
    brut = calculer_salaire_brut(ctx, _calendrier_heures(*NOVEMBRE), *NOVEMBRE, _retenue_ap(70.0, taux),
                                 jours_maintien=set())
    assert _prime(brut) == PLEIN_HEURES  # versée en entier : elle paie déjà les heures chômées
    assert getattr(ctx, "prime_anciennete_plein_mois", None) is None
    assert _indemnite(_calcul(70.0, taux), getattr(ctx, "prime_anciennete_plein_mois", None)) == _indemnite(
        _calcul(70.0, taux), None)


def test_forfait_reduit_prorata_actif():
    ctx = _contexte(forfait=True, jours_forfait=109)
    cal = [j for j in _calendrier_forfait(*PERIODE_19_JOURS, {11: FERIE})
           if j["date_complete"] not in ("2026-11-23", "2026-11-24")]
    taux = round(SALAIRE / (22 * 109 / 218) / 7, 4)
    brut = calculer_salaire_brut_forfait(ctx, cal, *PERIODE_19_JOURS, _retenue_ap(14.0, taux), jours_maintien=set())
    mois_travaille = round(PLEIN_FORFAIT * 0.5, 2)
    assert ctx.prime_anciennete_plein_mois == mois_travaille
    prime_brut = _prime(brut)
    assert prime_brut == round(PLEIN_FORFAIT * round(0.5 * 17 / 19, 6), 2)
    part = _indemnite(_calcul(14.0, taux), mois_travaille) - _indemnite(_calcul(14.0, taux), None)
    assert part > 0


def test_forfait_sans_prorata_la_prime_n_entre_pas_dans_l_indemnite():
    ctx = _sans_prorata(_contexte(forfait=True))
    taux = round(SALAIRE / 22 / 7, 4)
    brut = calculer_salaire_brut_forfait(ctx, _calendrier_forfait(*PERIODE_19_JOURS, {11: FERIE}),
                                         *PERIODE_19_JOURS, _retenue_ap(14.0, taux), jours_maintien=set())
    assert _prime(brut) == PLEIN_FORFAIT
    assert getattr(ctx, "prime_anciennete_plein_mois", None) is None


SAISIE = {"prime_id": "prime_anciennete", "libelle": "Prime ancienneté", "montant": 90.0}


@pytest.mark.parametrize("forfait", [False, True], ids=["heures", "forfait_jours"])
def test_une_prime_saisie_qui_remplace_le_calcul_n_entre_pas_dans_l_assiette_et_le_bulletin_le_dit(forfait):
    ctx = _contexte(forfait=forfait)
    primes = [SAISIE, *_retenue_ap(14.0, 15.0)]
    if forfait:
        calculer_salaire_brut_forfait(ctx, _calendrier_forfait(*PERIODE_19_JOURS, {11: FERIE}),
                                      *PERIODE_19_JOURS, primes, jours_maintien=set())
    else:
        calculer_salaire_brut(ctx, _calendrier_heures(*NOVEMBRE), *NOVEMBRE, primes, jours_maintien=set())
    assert ctx.prime_anciennete_plein_mois is None
    codes = [a.get("code") for a in ctx.alertes_baremes]
    assert "activite_partielle_sans_prime_saisie" in codes
    assert "prime_anciennete_remplacee" in codes


@pytest.mark.parametrize("forfait", [False, True], ids=["heures", "forfait_jours"])
def test_une_prime_saisie_sans_activite_partielle_ne_donne_pas_d_alerte(forfait):
    ctx = _contexte(forfait=forfait)
    if forfait:
        calculer_salaire_brut_forfait(ctx, _calendrier_forfait(*PERIODE_19_JOURS, {11: FERIE}),
                                      *PERIODE_19_JOURS, [SAISIE], jours_maintien=set())
    else:
        calculer_salaire_brut(ctx, _calendrier_heures(*NOVEMBRE), *NOVEMBRE, [SAISIE], jours_maintien=set())
    assert "activite_partielle_sans_prime_saisie" not in [a.get("code") for a in ctx.alertes_baremes]

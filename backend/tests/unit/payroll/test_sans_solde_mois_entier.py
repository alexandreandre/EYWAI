"""Mois entier sans solde : le brut tombe à 0, au forfait comme en heures (A2, 17/11).

Au forfait jours, sur une période du 21/09 au 25/10, 25 jours de retenue
(25 × salaire / 21,67) dépassaient le salaire ; la ligne « retenue ramenée au
salaire du mois » rendait le trop en gain, puis le plafond des retenues le
rendait une seconde fois : 645,50 € de brut restaient pour un mois sans travail.
"""

from __future__ import annotations

import calendar
from datetime import date

import pytest

from tests.unit.payroll.profils_salaries import ANNEE, PROFILS, banc  # noqa: F401

pytestmark = pytest.mark.unit


def _sans_solde(annee: int, mois: int) -> dict[int, str]:
    return {
        j: "absence_non_remuneree"
        for j in range(1, calendar.monthrange(annee, mois)[1] + 1)
        if date(annee, mois, j).weekday() < 5
    }


def _periode_entiere_sans_solde(banc, profil: str, mois: int, **k) -> dict:  # noqa: F811
    voisins = {(ANNEE, mois - 1): _sans_solde(ANNEE, mois - 1), (ANNEE, mois + 1): _sans_solde(ANNEE, mois + 1)}
    return banc.generer(profil, jours=_sans_solde(ANNEE, mois), jours_des_mois_voisins=voisins, mois=mois, **k)


def _brut_du_salaire(donnees: dict) -> float:
    """Le salaire de base moins ses retenues, tel que le bulletin l'affiche."""
    lignes = (donnees.get("calcul_du_brut") or []) + (donnees.get("details_absences") or [])
    return round(sum(float(l.get("gain") or 0) - float(l.get("perte") or 0) for l in lignes), 2)


@pytest.mark.parametrize("mois", (3, 10))
@pytest.mark.parametrize("profil", ("heures", "forfait_jours", "apprenti", "temps_partiel"))
def test_un_mois_entier_sans_solde_ne_laisse_aucun_brut(banc, profil, mois):  # noqa: F811
    donnees = _periode_entiere_sans_solde(banc, profil, mois)

    assert float(donnees.get("salaire_brut") or 0.0) == pytest.approx(0.0, abs=0.01)


@pytest.mark.parametrize("profil", PROFILS)
def test_le_brut_annonce_est_celui_des_lignes(banc, profil):  # noqa: F811
    """Les lignes du salaire et des absences se soldent à 0. Le brut lui-même
    (test au-dessus) hors sortie : un CDD qui finit garde ses indemnités de fin
    de contrat (congés, précarité)."""
    donnees = _periode_entiere_sans_solde(banc, profil, 10)

    assert _brut_du_salaire(donnees) == pytest.approx(0.0, abs=0.01)

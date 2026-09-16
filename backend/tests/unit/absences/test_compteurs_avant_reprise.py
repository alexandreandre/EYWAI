"""Compteurs de congés d'un bulletin antérieur à la reprise des soldes.

Les compteurs se calculent à partir d'un solde de départ daté : chez Colorplast,
le 31 août 2026, repris de la feuille du service paie. Les congés antérieurs à
cette date sont réputés déjà absorbés dans ce solde et ne sont pas redécomptés.

Un bulletin de janvier 2026 refabriqué demande donc au calcul de remonter le
temps, ce qu'il ne sait pas faire : il additionne le solde de départ d'août à
une année entière d'acquisition et affiche 50 jours de solde pour 25 acquis et
0 pris. Un chiffre impossible, et qu'un salarié lirait comme un droit.

Tant que la période du bulletin précède la date de reprise, aucun compteur n'est
produit : la case reste vide, ce qui est la vérité — on ne sait pas.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.absences.application import queries

pytestmark = pytest.mark.unit

EMPLOYE = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def reprise_fin_aout(monkeypatch):
    monkeypatch.setattr(queries, "_parse_hire_date", lambda _id: date(2022, 12, 1))
    monkeypatch.setattr(
        queries,
        "get_cp_opening_reference_dates",
        lambda ids: {EMPLOYE: date(2026, 8, 31)},
        raising=False,
    )


class _CalculLance(Exception):
    """Sentinelle : le calcul a bien démarré, on l'arrête avant tout accès réseau."""


@pytest.fixture
def calcul_observe(monkeypatch):
    """Observe l'entrée dans le calcul sans le dérouler : la suite de la
    fonction interroge Supabase (crédits de repos, politique de congés,
    société…), hors de portée d'un test unitaire hermétique."""
    appels: list = []

    def _stop(ids):
        appels.append(ids)
        raise _CalculLance

    monkeypatch.setattr(
        queries.absence_repository, "list_validated_for_employees", _stop
    )
    return appels


def test_un_bulletin_anterieur_a_la_reprise_ne_produit_aucun_compteur(reprise_fin_aout):
    assert queries.get_absence_balances_for_payslip(EMPLOYE, 2026, 1) is None


def test_le_mois_de_la_reprise_elle_meme_est_produit(reprise_fin_aout, calcul_observe):
    """Août se termine le 31 : la date de reprise est atteinte, on calcule."""
    with pytest.raises(_CalculLance):
        queries.get_absence_balances_for_payslip(EMPLOYE, 2026, 8)
    assert calcul_observe == [[EMPLOYE]], "le calcul aurait dû être lancé"


def test_sans_reprise_datee_le_comportement_ne_change_pas(monkeypatch, calcul_observe):
    monkeypatch.setattr(queries, "_parse_hire_date", lambda _id: date(2022, 12, 1))
    monkeypatch.setattr(
        queries, "get_cp_opening_reference_dates", lambda ids: {}, raising=False
    )
    with pytest.raises(_CalculLance):
        queries.get_absence_balances_for_payslip(EMPLOYE, 2026, 1)
    assert calcul_observe == [[EMPLOYE]], (
        "sans date de reprise, rien ne doit être bloqué"
    )

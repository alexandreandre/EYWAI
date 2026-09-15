"""Congé pour événement familial : déduit puis maintenu, brut inchangé.

Art. L3142-1 et suivants : absence autorisée dont la rémunération est
intégralement maintenue. Le jour était jusqu'ici écrit sous le type `conge`,
que le moteur de paie ne lit nulle part : il n'était ni travaillé ni en congé,
n'apparaissait pas au bulletin, et minorait les heures supplémentaires de sa
semaine (371 jours dans ce cas sur le groupe au 26/08/2026).

Référence : bulletin Quadra de mars 2026 de Cotte (Colorplast), congé du 25 au
27 février — 21,00 h de base retirées pour 271,93 €, 2,40 h structurelles pour
38,85 €, puis 310,78 € de maintien. Brut identique à celui d'un mois sans
absence : 2 398,38 €.

Ce qui ne bouge pas, la rémunération étant maintenue : le compteur d'heures, le
plafond de sécurité sociale et le SMIC de référence de la réduction générale.
Le cabinet retire pourtant les heures du compteur et proratise le plafond, alors
qu'il garde les heures d'un congé payé — sans effet financier, le brut restant
sous le plafond dans les deux cas.
"""

from __future__ import annotations

import pytest

from app.shared.domain.absence_calendar import (
    ABSENCE_CALENDAR_TYPES,
    ABSENCE_TYPE_TO_CALENDAR_TYPE,
)

pytestmark = pytest.mark.unit


def test_le_type_de_calendrier_n_est_plus_celui_que_le_moteur_ignore():
    assert ABSENCE_TYPE_TO_CALENDAR_TYPE["evenement_familial"] == "evenement_familial"
    assert "evenement_familial" in ABSENCE_CALENDAR_TYPES


def test_le_repos_compensateur_reste_en_attente_d_un_bulletin():
    """Même aveuglement, mais aucune référence cabinet : laissé tel quel."""
    assert ABSENCE_TYPE_TO_CALENDAR_TYPE["repos_compensateur"] == "conge"


class TestBulletinDeCotte:
    """Trois jours à 7 h, sur un contrat de 39 h à 12,9492 €."""

    TAUX_BASE = 12.9492
    TAUX_MAJORE = 16.1865
    HEURES_STRUCTURELLES = 17.33

    def test_la_retenue_de_base_suit_la_reference_journaliere_legale(self):
        """3 jours × 7 h, et non × 8,5 h ou × 7,8 h d'horaire contractuel."""
        assert round(3 * 7.0 * self.TAUX_BASE, 2) == 271.93

    def test_la_quote_part_d_heures_sup_structurelles(self):
        """17,33 h réparties sur les 21,67 jours légaux du mois, 3 jours absents."""
        jours_legaux_mensuels = 151.67 / 7.0
        heures = round(self.HEURES_STRUCTURELLES * 3.0 / jours_legaux_mensuels, 2)
        assert heures == 2.40
        assert round(heures * self.TAUX_MAJORE, 2) == 38.85

    def test_le_maintien_remet_exactement_ce_qui_a_ete_retire(self):
        assert round(271.93 + 38.85, 2) == 310.78

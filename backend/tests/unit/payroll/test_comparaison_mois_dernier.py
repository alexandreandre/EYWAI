"""Comparaison brut / net / heures sup / absences avec le bulletin du mois précédent."""

from __future__ import annotations

import pytest

from app.modules.payroll.domain.comparaison_mois_dernier import (
    TEXTE_ABSENT,
    comparer_au_mois_dernier,
)

pytestmark = pytest.mark.unit


def _bulletin(*, brut: float, net: float, hs: float | None = None, absences: float | None = None) -> dict:
    brut_lignes = [{"libelle": "Salaire de base", "gain": brut, "quantite": 151.67}]
    if hs:
        brut_lignes.append(
            {
                "libelle": "Heures suppl. majorées à 25%",
                "quantite": hs,
                "gain": hs * 16,
            }
        )
    return {
        "salaire_brut": brut,
        "net_a_payer": net,
        "calcul_du_brut": brut_lignes,
        "details_absences": (
            [{"libelle": "Absence arrêt maladie du 01/04 au 05/04", "quantite": absences, "perte": 100.0}]
            if absences
            else []
        ),
        "details_conges": [],
    }


def test_sans_bulletin_le_mois_dernier_aucun_chiffre_invente():
    actuel = _bulletin(brut=2100.0, net=1600.0, hs=8.0)
    cmp_ = comparer_au_mois_dernier(actuel, None)
    assert cmp_["present"] is False
    assert cmp_["texte"] == TEXTE_ABSENT
    assert "brut" not in cmp_ or cmp_.get("brut") is None
    assert "€" not in cmp_["texte"]
    assert "→" not in cmp_["texte"]


def test_compare_brut_net_heures_sup_et_absences():
    actuel = _bulletin(brut=2100.0, net=1600.0, hs=12.0, absences=14.0)
    precedent = _bulletin(brut=2000.0, net=1500.0, hs=8.0)
    cmp_ = comparer_au_mois_dernier(actuel, precedent)
    assert cmp_["present"] is True
    assert cmp_["brut"] == {"avant": 2000.0, "apres": 2100.0}
    assert cmp_["net"] == {"avant": 1500.0, "apres": 1600.0}
    assert cmp_["heures_sup"] == {"avant": 8.0, "apres": 12.0}
    assert cmp_["absences"] == {"avant": 0.0, "apres": 14.0}
    assert cmp_["texte"] == (
        "Brut : 2 000,00 € → 2 100,00 €"
        " · Net : 1 500,00 € → 1 600,00 €"
        " · Heures sup : 8 h → 12 h"
        " · Absences : 0 h → 14 h"
    )


def test_un_precedent_sans_heures_sup_vaut_zero_heures():
    actuel = _bulletin(brut=2000.0, net=1500.0, hs=4.0)
    precedent = _bulletin(brut=2000.0, net=1500.0)
    cmp_ = comparer_au_mois_dernier(actuel, precedent)
    assert cmp_["heures_sup"] == {"avant": 0.0, "apres": 4.0}


def test_mois_precedent_civil():
    from app.modules.payroll.domain.comparaison_mois_dernier import mois_precedent_civil

    assert mois_precedent_civil(2026, 3) == (2026, 2)
    assert mois_precedent_civil(2026, 1) == (2025, 12)

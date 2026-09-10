"""La date de paiement ne dépend plus de l'arrêté des variables."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.bulletin import _calculer_date_paiement

pytestmark = pytest.mark.unit


class _Contexte:
    """Le strict nécessaire : `_calculer_date_paiement` ne lit que l'entreprise."""

    def __init__(self, periode_de_paie: dict, date_paiement: str | None = None):
        parametres: dict = {"periode_de_paie": periode_de_paie}
        if date_paiement is not None:
            parametres["date_paiement"] = date_paiement
        self.entreprise = {"parametres_paie": parametres}


def test_sans_reglage_le_comportement_est_inchange_arrete_glissant():
    """Colorplast (4, -2) : avant-dernier vendredi, comme aujourd'hui."""
    contexte = _Contexte({"jour_de_fin": 4, "occurrence": -2})
    assert _calculer_date_paiement(contexte, 2026, 5) == "2026-05-22"


def test_sans_reglage_le_comportement_est_inchange_mois_civil():
    contexte = _Contexte({"jour_de_fin": 31, "occurrence": -1})
    assert _calculer_date_paiement(contexte, 2026, 5) == "2026-05-31"


def test_dernier_jour_du_mois_malgre_un_arrete_glissant():
    """Ce que Gaëlle décrit : variables décalées, mais paiement le 31."""
    contexte = _Contexte({"jour_de_fin": 4, "occurrence": -2}, date_paiement="dernier_jour_du_mois")
    assert _calculer_date_paiement(contexte, 2026, 5) == "2026-05-31"
    assert _calculer_date_paiement(contexte, 2026, 2) == "2026-02-28"


def test_le_reglage_explicite_arrete_glissant_reste_possible():
    contexte = _Contexte({"jour_de_fin": 4, "occurrence": -2}, date_paiement="arrete_des_variables")
    assert _calculer_date_paiement(contexte, 2026, 5) == "2026-05-22"


def test_un_reglage_inconnu_ne_casse_rien():
    """Une valeur inattendue en base ne doit pas faire tomber un bulletin."""
    contexte = _Contexte({"jour_de_fin": 4, "occurrence": -2}, date_paiement="n_importe_quoi")
    assert _calculer_date_paiement(contexte, 2026, 5) == "2026-05-22"

"""Les heures rémunérées du mois retirent les absences retenues par la
fenêtre, pas celles de tout le calendrier étendu.

Colorplast, juillet 2026 : le calendrier étendu va du 22/06 au 31/07. Les
absences du 27 au 31 juillet appartiennent à la paie d'août ; les compter ici
faussait le compteur « cumul heures » du bulletin (retour Gaëlle du 14/09).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.payroll.documents.payslip_run_common import (
    heures_remunerees_mois_contrat,
)

pytestmark = pytest.mark.unit


def _contexte(duree_hebdo: float) -> SimpleNamespace:
    return SimpleNamespace(duree_hebdo_contrat=duree_hebdo)


def test_contrat_39h_sans_absence():
    assert heures_remunerees_mois_contrat(_contexte(39.0), []) == pytest.approx(169.0)


def test_seules_les_absences_transmises_sont_retirees():
    """L'appelant transmet les événements déjà filtrés par la fenêtre."""
    retenus = [
        {"date_complete": "2026-07-08", "type": "absence_injustifiee_base", "heures": 2.5},
        {"date_complete": "2026-07-15", "type": "absence_injustifiee_base", "heures": 7.0},
        {"date_complete": "2026-07-20", "type": "absence_injustifiee_hs25", "heures": 8.5},
        {"date_complete": "2026-07-13", "type": "conges_payes", "heures": 7.0},
    ]
    assert heures_remunerees_mois_contrat(_contexte(39.0), retenus) == pytest.approx(151.0)

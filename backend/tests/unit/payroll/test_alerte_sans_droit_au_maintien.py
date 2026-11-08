"""Pas de maintien faute d'ancienneté : une information, pas une alerte (Elsa, 05/11).

Martine applique la convention et la RH n'a rien à faire. Le motif reste à
l'aperçu de l'arrêt, au détail du maintien et sous la ligne d'absence.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.bulletin import alertes_maintien_du_bulletin

pytestmark = pytest.mark.unit

MOTIF = "Plasturgie : un an d'ancienneté requis pour une maladie (0 mois au début de l'arrêt)."


def test_le_motif_sans_droit_n_est_pas_une_alerte():
    assert alertes_maintien_du_bulletin(
        {"alertes": [MOTIF, "Statut à compléter."], "maintien": {"motif_non_maintien": MOTIF}}
    ) == ["Statut à compléter."]


def test_les_autres_alertes_restent():
    assert alertes_maintien_du_bulletin({"alertes": ["A"], "maintien": {}}) == ["A"]
    assert alertes_maintien_du_bulletin({}) == []

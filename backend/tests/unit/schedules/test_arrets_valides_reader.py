"""Lecture des arrêts validés : la seule source fiable des week-ends d'un arrêt.

La validation d'un arrêt ne retype pas ses week-ends, repos et fériés ; les
métadonnées qu'elle y pose sont effacées à la première sauvegarde du planning
(`merge_planned_entries` retire les clés serveur d'un jour non absence). Le
lecteur rend donc les demandes d'arrêt validées, par salarié. Supabase est moqué.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.schedules.infrastructure.arrets_valides import ArretsValidesReader

pytestmark = pytest.mark.unit


def _supabase(lignes: list[dict]) -> MagicMock:
    client = MagicMock()
    requete = client.table.return_value.select.return_value.in_.return_value.eq.return_value
    requete.execute.return_value = MagicMock(data=lignes)
    return client


def test_rend_les_arrets_valides_qui_touchent_la_periode_par_salarie():
    lignes = [
        {"employee_id": "e1", "type": "arret_maladie", "status": "validated", "selected_days": ["2026-09-12"]},
        {"employee_id": "e1", "type": "conge_paye", "status": "validated", "selected_days": ["2026-09-13"]},
        {"employee_id": "e2", "type": "arret_at", "status": "validated", "selected_days": ["2026-08-30", "2026-09-01"]},
        {"employee_id": "e2", "type": "arret_maladie", "status": "validated", "selected_days": ["2026-07-01"]},
    ]
    client = _supabase(lignes)
    with patch("app.modules.schedules.infrastructure.arrets_valides.supabase", client):
        arrets = ArretsValidesReader().par_salarie(["e1", "e2"], date(2026, 9, 1), date(2026, 9, 30))

    assert arrets == {"e1": [lignes[0]], "e2": [lignes[2]]}
    client.table.assert_called_once_with("absence_requests")
    # Le type se trie en Python, jamais en SQL : un filtre sur l'enum PostgreSQL
    # fait échouer toute la requête dès qu'un libellé manque (07/09/2026).
    client.table.return_value.select.return_value.in_.return_value.eq.assert_called_once_with(
        "status", "validated"
    )


def test_aucun_salarie_aucune_lecture():
    client = _supabase([])
    with patch("app.modules.schedules.infrastructure.arrets_valides.supabase", client):
        assert ArretsValidesReader().par_salarie([], date(2026, 9, 1), date(2026, 9, 30)) == {}

    client.table.assert_not_called()

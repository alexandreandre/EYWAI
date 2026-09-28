"""Le bulletin dit quels exports du mois ont déjà été faits."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.payslips.application import exports_du_mois as mod

pytestmark = pytest.mark.unit


def _avec(lignes):
    client = MagicMock()
    client.table.return_value.select.return_value.match.return_value.execute.return_value = MagicMock(data=lignes)
    return patch.object(mod, "supabase", client), client


def test_un_export_par_type_le_plus_recent_dans_l_ordre():
    ctx, client = _avec(
        [
            {"export_type": "virement_salaires", "generated_at": "2026-09-05T10:00:00"},
            {"export_type": "journal_paie", "generated_at": "2026-09-03T10:00:00"},
            {"export_type": "journal_paie", "generated_at": "2026-09-06T09:00:00"},
        ]
    )
    with ctx:
        exports = mod.exports_du_mois("c1", 2026, 8)
    client.table.return_value.select.return_value.match.assert_called_once_with(
        {"company_id": "c1", "period": "2026-08", "status": "generated"}
    )
    assert exports == [
        {"type": "virement_salaires", "libelle": "Paiement des salaires (virement)", "date": "2026-09-05T10:00:00"},
        {"type": "journal_paie", "libelle": "Journal de paie", "date": "2026-09-06T09:00:00"},
    ]


def test_aucun_export_liste_vide():
    ctx, _ = _avec([])
    with ctx:
        assert mod.exports_du_mois("c1", 2026, 8) == []


def test_une_lecture_impossible_ne_casse_pas_l_ecran():
    client = MagicMock()
    client.table.side_effect = RuntimeError("base indisponible")
    with patch.object(mod, "supabase", client):
        assert mod.exports_du_mois("c1", 2026, 8) == []

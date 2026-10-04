"""Le bulletin dit quels exports du mois ont déjà été faits, et lesquels sont à refaire."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.payslips.application import exports_du_mois as mod

pytestmark = pytest.mark.unit


def _avec(lignes, a_refaire=frozenset()):
    client = MagicMock()
    client.table.return_value.select.return_value.match.return_value.execute.return_value = MagicMock(data=lignes)
    juge = MagicMock(return_value=set(a_refaire))
    return patch.object(mod, "supabase", client), patch.object(mod, "ids_des_exports_a_refaire", juge), client, juge


def _ligne(id_, type_, date):
    return {"id": id_, "export_type": type_, "period": "2026-08", "status": "generated", "generated_at": date}


def test_un_export_par_type_le_plus_recent_dans_l_ordre():
    lignes = [
        _ligne("v", "virement_salaires", "2026-09-05T10:00:00"),
        _ligne("j1", "journal_paie", "2026-09-03T10:00:00"),
        _ligne("j2", "journal_paie", "2026-09-06T09:00:00"),
    ]
    ctx, juge_ctx, client, _ = _avec(lignes)
    with ctx, juge_ctx:
        exports = mod.exports_du_mois("c1", 2026, 8)
    client.table.return_value.select.assert_called_once_with("id, export_type, period, status, generated_at")
    client.table.return_value.select.return_value.match.assert_called_once_with(
        {"company_id": "c1", "period": "2026-08", "status": "generated"}
    )
    assert exports == [
        {
            "type": "virement_salaires",
            "libelle": "Paiement des salaires (virement)",
            "date": "2026-09-05T10:00:00",
            "a_refaire": False,
        },
        {"type": "journal_paie", "libelle": "Journal de paie", "date": "2026-09-06T09:00:00", "a_refaire": False},
    ]


def test_un_export_fait_avant_un_bulletin_recalcule_est_a_refaire():
    lignes = [
        _ligne("v", "virement_salaires", "2026-09-05T10:00:00"),
        _ligne("j", "journal_paie", "2026-09-06T09:00:00"),
    ]
    ctx, juge_ctx, _, juge = _avec(lignes, a_refaire={"v"})
    with ctx, juge_ctx:
        exports = mod.exports_du_mois("c1", 2026, 8)

    juge.assert_called_once_with("c1", lignes)
    assert [(e["type"], e["a_refaire"]) for e in exports] == [
        ("virement_salaires", True),
        ("journal_paie", False),
    ]


def test_aucun_export_liste_vide():
    ctx, juge_ctx, _, juge = _avec([])
    with ctx, juge_ctx:
        assert mod.exports_du_mois("c1", 2026, 8) == []
    juge.assert_not_called()


def test_une_lecture_impossible_ne_casse_pas_l_ecran():
    client = MagicMock()
    client.table.side_effect = RuntimeError("base indisponible")
    with patch.object(mod, "supabase", client):
        assert mod.exports_du_mois("c1", 2026, 8) == []

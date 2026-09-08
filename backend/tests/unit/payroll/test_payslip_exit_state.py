"""Tests résolution indemnités de sortie pour bulletin."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from app.modules.payroll.documents.payslip_run_common import (
    resolve_exit_indemnities_for_payslip,
    resolve_exit_state_for_payslip,
)


def _mock_supabase(rows):
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.not_.in_.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=rows
    )
    return sb


def test_resolve_exit_state_avec_indemnites():
    rows = [
        {
            "last_working_day": "2025-09-30",
            "calculated_indemnities": {"indemnite_conges": {"montant": 500.0}},
        }
    ]
    indemnities, block = resolve_exit_state_for_payslip(
        "emp-1", 2025, 9, _mock_supabase(rows)
    )
    assert indemnities is not None
    assert block is False
    assert resolve_exit_indemnities_for_payslip("emp-1", 2025, 9, _mock_supabase(rows)) == indemnities


def test_resolve_exit_state_bloque_sans_indemnites():
    rows = [{"last_working_day": "2025-09-30", "calculated_indemnities": None}]
    indemnities, block = resolve_exit_state_for_payslip(
        "emp-1", 2025, 9, _mock_supabase(rows)
    )
    assert indemnities is None
    assert block is True


def test_resolve_exit_state_ignore_autre_mois():
    rows = [{"last_working_day": "2025-08-31", "calculated_indemnities": None}]
    indemnities, block = resolve_exit_state_for_payslip(
        "emp-1", 2025, 9, _mock_supabase(rows)
    )
    assert indemnities is None
    assert block is False


def test_resolve_exit_state_fenetre_periode_glissante():
    """Arrêté glissant : un CDD finissant le 30/06 est payé sur JUILLET
    (fenêtre 22/06→26/07) — le STC se rattache au bulletin de juillet."""
    rows = [
        {
            "exit_type": "fin_cdd",
            "last_working_day": "2026-06-30",
            "calculated_indemnities": {"indemnite_conges": {"montant": 120.0}},
        }
    ]
    indemnities, block = resolve_exit_state_for_payslip(
        "emp-1",
        2026,
        7,
        _mock_supabase(rows),
        date_debut_periode=date(2026, 6, 22),
        date_fin_periode=date(2026, 7, 26),
    )
    assert indemnities is not None
    assert block is False


def test_resolve_exit_state_fenetre_exclut_le_mois_civil():
    """Le même départ ne se rattache PAS au bulletin de juin : la fenêtre
    de juin (25/05→21/06) ne contient pas le 30/06."""
    rows = [
        {
            "exit_type": "fin_cdd",
            "last_working_day": "2026-06-30",
            "calculated_indemnities": None,
        }
    ]
    indemnities, block = resolve_exit_state_for_payslip(
        "emp-1",
        2026,
        6,
        _mock_supabase(rows),
        date_debut_periode=date(2026, 5, 25),
        date_fin_periode=date(2026, 6, 21),
    )
    assert indemnities is None
    assert block is False


def test_resolve_exit_state_ignore_transfert():
    """Un transfert intra-groupe n'a jamais de STC et ne bloque pas l'ICCP."""
    rows = [
        {
            "exit_type": "transfert",
            "last_working_day": "2026-02-28",
            "calculated_indemnities": None,
        }
    ]
    indemnities, block = resolve_exit_state_for_payslip(
        "emp-1", 2026, 2, _mock_supabase(rows)
    )
    assert indemnities is None
    assert block is False


def test_resolve_exit_state_transfert_saute_vrai_depart_resolu():
    """Le transfert est ignoré ; le vrai départ (fin de CDD) est bien résolu."""
    rows = [
        {
            "exit_type": "fin_cdd",
            "last_working_day": "2026-06-30",
            "calculated_indemnities": {"indemnite_conges": {"montant": 80.0}},
        },
        {
            "exit_type": "transfert",
            "last_working_day": "2026-02-28",
            "calculated_indemnities": None,
        },
    ]
    indemnities, block = resolve_exit_state_for_payslip(
        "emp-1", 2026, 6, _mock_supabase(rows)
    )
    assert indemnities is not None
    assert block is False

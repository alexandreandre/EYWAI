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


class _ContexteFinCdd:
    def __init__(self, is_cdd: bool, dernier_mois: bool, dossier, block: bool):
        self.is_cdd = is_cdd
        self._dernier_mois = dernier_mois
        self.exit_indemnities = dossier
        self.block_iccp_cdd = block

    def est_dernier_mois_cdd(self, debut, fin):
        return self.is_cdd and self._dernier_mois


def test_fin_cdd_retire_l_iccp_du_dossier_et_leve_le_blocage():
    """Demory, Colorplast, juillet 2026 : l'ICCP du dossier arrivait après
    les cotisations (net > brut) ; celle du brut, cotisée, doit prendre."""
    from app.modules.payroll.documents.payslip_run_common import (
        ecarter_iccp_du_dossier_pour_fin_cdd,
    )

    ctx = _ContexteFinCdd(
        True,
        True,
        {"indemnite_conges": {"montant": 1037.21}, "indemnite_preavis": {"montant": 0.0}},
        block=True,
    )
    ecarter_iccp_du_dossier_pour_fin_cdd(ctx, date(2026, 7, 1), date(2026, 7, 31))
    assert ctx.block_iccp_cdd is False
    assert "indemnite_conges" not in ctx.exit_indemnities
    assert ctx.exit_indemnities == {"indemnite_preavis": {"montant": 0.0}}


def test_fin_cdd_sans_dossier_leve_seulement_le_blocage():
    from app.modules.payroll.documents.payslip_run_common import (
        ecarter_iccp_du_dossier_pour_fin_cdd,
    )

    ctx = _ContexteFinCdd(True, True, None, block=True)
    ecarter_iccp_du_dossier_pour_fin_cdd(ctx, date(2026, 7, 1), date(2026, 7, 31))
    assert ctx.block_iccp_cdd is False
    assert ctx.exit_indemnities is None


def test_hors_fin_cdd_le_dossier_est_intact():
    from app.modules.payroll.documents.payslip_run_common import (
        ecarter_iccp_du_dossier_pour_fin_cdd,
    )

    dossier = {"indemnite_conges": {"montant": 500.0}}
    for ctx in (
        _ContexteFinCdd(False, False, dict(dossier), block=True),  # CDI
        _ContexteFinCdd(True, False, dict(dossier), block=True),  # CDD, pas le dernier mois
    ):
        ecarter_iccp_du_dossier_pour_fin_cdd(ctx, date(2026, 7, 1), date(2026, 7, 31))
        assert ctx.block_iccp_cdd is True
        assert ctx.exit_indemnities == dossier

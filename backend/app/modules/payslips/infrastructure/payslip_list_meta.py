"""Métadonnées légères extraites de payslip_data pour les listes API."""

from __future__ import annotations

from typing import Any

from app.modules.payroll.engine.controles_convention import (
    extraire_messages_alertes_rh,
)


def payslip_list_meta(payslip_data: Any) -> dict[str, Any]:
    """net_a_payer et alertes RH depuis payslip_data."""
    if not isinstance(payslip_data, dict):
        return {"net_a_payer": None, "warnings": []}

    net_amount = None
    val = payslip_data.get("net_a_payer")
    if isinstance(val, (int, float)):
        net_amount = float(val)

    return {
        "net_a_payer": net_amount,
        "warnings": extraire_messages_alertes_rh(payslip_data),
    }

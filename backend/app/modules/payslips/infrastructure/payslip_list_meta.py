"""Métadonnées légères extraites de payslip_data pour les listes API."""

from __future__ import annotations

from typing import Any

from app.modules.payroll.engine.controles_convention import (
    avertissements_de_generation,
)


def payslip_list_meta(payslip_data: Any) -> dict[str, Any]:
    """net_a_payer, alertes RH et points à arbitrer depuis payslip_data.

    Un point à arbitrer (plafond transport…) n'est pas une alerte : la liste le
    montre discrètement, hors du compte des alertes."""
    if not isinstance(payslip_data, dict):
        return {"net_a_payer": None, "warnings": [], "points_a_arbitrer": []}

    net_amount = None
    val = payslip_data.get("net_a_payer")
    if isinstance(val, (int, float)):
        net_amount = float(val)

    warnings: list[str] = []
    points_a_arbitrer: list[str] = []
    for avertissement in avertissements_de_generation(payslip_data):
        if isinstance(avertissement, str):
            warnings.append(avertissement)
        elif avertissement.get("severity") == "info":
            points_a_arbitrer.append(str(avertissement.get("message") or ""))
        else:
            warnings.append(str(avertissement.get("message") or ""))

    return {
        "net_a_payer": net_amount,
        "warnings": warnings,
        "points_a_arbitrer": points_a_arbitrer,
    }

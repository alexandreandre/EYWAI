"""Le salarié ne reçoit ni la comparaison ni les alertes internes de la RH.

« Mon bulletin » affichait l'onglet de comparaison avec les alertes de contrôle
(R03 critique, R08, R10…) : seuls les boutons étaient masqués côté écran. L'API
refuse maintenant la comparaison à tout compte qui n'est pas RH du bulletin, et
la tendance n'y porte plus d'alertes.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payslips.application import comparison_service as cs
from app.modules.payslips.application.dto import PayslipForbiddenError, UserContext

_BASE = "app.modules.payslips.application.comparison_service."


def _salarie() -> UserContext:
    return UserContext(
        user_id="emp-1",
        is_platform_admin=False,
        has_rh_access_in_company=lambda c: False,
        active_company_id="co-1",
    )


def _rh() -> UserContext:
    return UserContext(
        user_id="rh-1",
        is_platform_admin=False,
        has_rh_access_in_company=lambda c: c == "co-1",
        active_company_id="co-1",
    )


def _detail() -> dict:
    return {
        "id": "ps-1",
        "employee_id": "emp-1",
        "company_id": "co-1",
        "year": 2026,
        "month": 9,
        "status": "valide",
        "payslip_data": {"salaire_brut": 2000.0, "net_a_payer": 1550.0},
    }


def _patch_lectures(detail=None):
    return (
        patch(_BASE + "get_payslip_details", return_value=detail or _detail()),
        patch(_BASE + "fetch_previous_validated_payslip", return_value=None),
        patch(_BASE + "fetch_employee_statut", return_value=None),
        patch(_BASE + "fetch_recent_nets_asc_for_r10", return_value=[]),
    )


def test_le_salarie_n_a_pas_la_comparaison_de_son_bulletin():
    a, b, c, d = _patch_lectures()
    with a, b, c, d, pytest.raises(PayslipForbiddenError):
        cs.get_payslip_comparison_for_user("ps-1", _salarie())


def test_la_rh_garde_la_comparaison():
    a, b, c, d = _patch_lectures()
    with a, b, c, d:
        resultat = cs.get_payslip_comparison_for_user("ps-1", _rh())
    assert "alerts" in resultat


def test_la_tendance_du_salarie_ne_porte_aucune_alerte():
    precedent = {
        "id": "ps-0",
        "year": 2026,
        "month": 8,
        "payslip_data": {"salaire_brut": 2000.0, "net_a_payer": 1000.0},
    }
    mois_passes = [
        {**precedent, "id": "ps-a", "month": 7, "payslip_data": {"salaire_brut": 2000.0, "net_a_payer": 1550.0}},
        precedent,
    ]
    with (
        patch(_BASE + "get_payslip_details", return_value=_detail()),
        patch(_BASE + "fetch_validated_payslips_strictly_before", return_value=list(reversed(mois_passes))),
        patch(_BASE + "fetch_employee_statut", return_value=None),
    ):
        vu_salarie = cs.get_payslip_trend_for_user("ps-1", _salarie())
        vu_rh = cs.get_payslip_trend_for_user("ps-1", _rh())
    assert all(m["alerts"] == [] for m in vu_salarie["months"])
    assert any(m["alerts"] for m in vu_rh["months"])

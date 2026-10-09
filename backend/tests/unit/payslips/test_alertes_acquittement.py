"""Acquitter ou ignorer une alerte : règle connue exigée, action tracée.

Le code de règle de l'URL n'était pas validé (« R99 » était accepté et stocké),
et seule la validation du bulletin laissait une trace au journal d'audit.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.payslips.api import router as r
from app.modules.payslips.schemas import AcquitAlertRequest

_R = "app.modules.payslips.api.router."


def _utilisateur():
    return SimpleNamespace(id="user-1", email="rh@exemple.fr", active_company_id="co-1")


def _requete():
    return SimpleNamespace(client=SimpleNamespace(host="10.0.0.1"))


def _appel(route, rule_id: str, commentaire: str | None = None):
    return route(
        "ps-1",
        rule_id,
        request=_requete(),
        body=AcquitAlertRequest(comment=commentaire),
        current_user=_utilisateur(),
    )


@pytest.mark.parametrize("route", [r.acquit_payslip_alert_route, r.ignore_payslip_alert_route])
def test_un_code_de_regle_inconnu_est_refuse_en_422(route):
    with (
        patch(_R + "acquit_payslip_alert_for_user") as acquit,
        patch(_R + "ignore_payslip_alert_for_user") as ignore,
        patch(_R + "_to_user_context"),
        pytest.raises(HTTPException) as exc,
    ):
        _appel(route, "R99")
    assert exc.value.status_code == 422
    acquit.assert_not_called()
    ignore.assert_not_called()


def test_une_regle_connue_est_acceptee():
    with (
        patch(_R + "acquit_payslip_alert_for_user"),
        patch(_R + "_to_user_context"),
        patch(_R + "get_payslip_meta_for_access", return_value={"company_id": "co-1", "employee_id": "emp-1"}),
        patch(_R + "log_audit_event"),
    ):
        assert _appel(r.acquit_payslip_alert_route, "R03")["status"] == "acquittee"


@pytest.mark.parametrize(
    "route,action,service",
    [
        (r.acquit_payslip_alert_route, "payslip.alert_acquit", "acquit_payslip_alert_for_user"),
        (r.ignore_payslip_alert_route, "payslip.alert_ignore", "ignore_payslip_alert_for_user"),
    ],
)
def test_l_action_laisse_une_trace_qui_quand_quelle_regle_quel_commentaire(route, action, service):
    journal = MagicMock()
    with (
        patch(_R + service),
        patch(_R + "_to_user_context"),
        patch(_R + "get_payslip_meta_for_access", return_value={"company_id": "co-1", "employee_id": "emp-1"}),
        patch(_R + "log_audit_event", journal),
    ):
        _appel(route, "R03", "Prime exceptionnelle confirmée")
    journal.assert_called_once()
    kw = journal.call_args.kwargs
    assert kw["company_id"] == "co-1"
    assert kw["user_id"] == "user-1"
    assert kw["user_email"] == "rh@exemple.fr"
    assert kw["action"] == action
    assert kw["resource_type"] == "payslip"
    assert kw["resource_id"] == "ps-1"
    assert kw["details"] == {
        "employee_id": "emp-1",
        "rule_id": "R03",
        "comment": "Prime exceptionnelle confirmée",
    }


def test_pas_de_trace_quand_l_action_est_refusee():
    journal = MagicMock()
    with (
        patch(_R + "acquit_payslip_alert_for_user", side_effect=ValueError("boom")),
        patch(_R + "_to_user_context"),
        patch(_R + "get_payslip_meta_for_access", return_value={"company_id": "co-1"}),
        patch(_R + "log_audit_event", journal),
        pytest.raises(HTTPException),
    ):
        _appel(r.acquit_payslip_alert_route, "R03")
    journal.assert_not_called()


def test_les_actions_ont_un_libelle_dans_le_journal():
    from app.modules.audit.infrastructure.repository import ACTIONS_LABELS

    assert ACTIONS_LABELS["payslip.alert_acquit"] == "Acquittement d'une alerte de bulletin"
    assert ACTIONS_LABELS["payslip.alert_ignore"] == "Alerte de bulletin ignorée"

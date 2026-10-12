from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.saisies_avances.api.router import (
    _filter_company_rows_in_scope,
    _require_advance_scope,
)


def test_advances_filter_keeps_only_active_company_rows():
    user = SimpleNamespace(
        id="user-1",
        is_platform_admin=False,
        has_rh_access_in_company=lambda _cid: False,
    )
    rows = [
        {"company_id": "company-1", "employee_id": "emp-a"},
        {"company_id": "company-2", "employee_id": "emp-b"},
    ]
    with patch(
        "app.modules.saisies_avances.api.router.access_control_service.filter_allowed_employee_ids",
        return_value=["emp-a"],
    ):
        filtered = _filter_company_rows_in_scope(
            user, "company-1", "advances.view_all", rows
        )

    assert filtered == [{"company_id": "company-1", "employee_id": "emp-a"}]


def test_advance_scope_hides_cross_company_record():
    user = SimpleNamespace(id="user-1", is_platform_admin=False)
    with patch(
        "app.modules.saisies_avances.api.router.queries.get_salary_advance",
        return_value={"company_id": "company-2", "employee_id": "emp-1"},
    ):
        with pytest.raises(HTTPException) as exc:
            _require_advance_scope(user, "company-1", "adv-1", "advances.view_all")

    assert exc.value.status_code == 404


def _paiement_tel_que_lu():
    """Le paiement tel que `get_payment_with_advance` le lit en base : la
    jointure de l'avance ne porte que id, approved_amount et remaining_amount."""
    return {
        "id": "pay-1",
        "advance_id": "adv-1",
        "company_id": "company-1",
        "payment_amount": 300.0,
        "proof_file_path": "user-1/preuve.pdf",
        "advance": {"id": "adv-1", "approved_amount": 300.0, "remaining_amount": 300.0},
    }


def test_payment_scope_lit_la_societe_et_le_salarie_de_l_avance():
    """Suppression d'un versement d'avance (rejeu G.2) : le paiement existe et
    appartient à la société active ; la portée ne doit pas répondre 404."""
    from app.modules.saisies_avances.api.router import _require_payment_scope

    user = SimpleNamespace(id="user-1", is_platform_admin=False)
    with patch(
        "app.modules.saisies_avances.api.router.queries.get_payment_with_advance",
        return_value=_paiement_tel_que_lu(),
    ), patch(
        "app.modules.saisies_avances.api.router.queries.get_salary_advance",
        return_value={"id": "adv-1", "company_id": "company-1", "employee_id": "emp-1"},
    ), patch(
        "app.modules.saisies_avances.api.router.access_control_service.require_employee_access",
    ) as acces:
        _require_payment_scope(user, "company-1", "pay-1", "advances.manage")

    acces.assert_called_once()
    valeurs = [str(a) for a in acces.call_args.args] + [
        str(v) for v in acces.call_args.kwargs.values()
    ]
    assert "emp-1" in valeurs


def test_payment_scope_cache_le_paiement_d_une_autre_societe():
    from app.modules.saisies_avances.api.router import _require_payment_scope

    user = SimpleNamespace(id="user-1", is_platform_admin=False)
    paiement = _paiement_tel_que_lu() | {"company_id": "company-2"}
    with patch(
        "app.modules.saisies_avances.api.router.queries.get_payment_with_advance",
        return_value=paiement,
    ), patch(
        "app.modules.saisies_avances.api.router.queries.get_salary_advance",
        return_value={"id": "adv-1", "company_id": "company-2", "employee_id": "emp-1"},
    ):
        with pytest.raises(HTTPException) as exc:
            _require_payment_scope(user, "company-1", "pay-1", "advances.manage")

    assert exc.value.status_code == 404

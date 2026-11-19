"""Une note saisie sur le mauvais salarié se rattache au bon (Elsa, 17/11).

Avant, seul le montant (et la date, le type, la description) se modifiait :
il fallait supprimer la note et la refaire avec son justificatif.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.expenses.api import router
from app.modules.expenses.application.commands import update_expense
from app.modules.expenses.application.dto import UpdateExpenseInput
from app.modules.expenses.schemas.requests import ExpenseUpdateRequest

pytestmark = pytest.mark.unit

NOTE = {"id": "n-1", "employee_id": "e-1", "company_id": "co-1", "amount": 42.0, "vat_rate": 10.0}


class TestCommande:
    def _maj(self, **champs):
        repo = MagicMock()
        repo.update.side_effect = lambda _id, payload: {**NOTE, **payload}
        with patch("app.modules.expenses.application.commands.ExpenseRepository", return_value=repo):
            update_expense(UpdateExpenseInput(expense_id="n-1", **champs), existing=dict(NOTE))
        return repo

    def test_le_salarie_change_seul(self):
        repo = self._maj(employee_id="e-2")
        repo.update.assert_called_once_with("n-1", {"employee_id": "e-2"})

    def test_le_meme_salarie_ne_reecrit_rien(self):
        repo = self._maj(employee_id="e-1")
        repo.update.assert_not_called()


class TestRoute:
    def _appel(self, societe_du_nouveau, acces_refuse=False):
        service = MagicMock()
        service.get_employee_company_id.return_value = societe_du_nouveau
        service.update_expense.return_value = {**NOTE, "employee_id": "e-2"}
        acces = MagicMock()
        if acces_refuse:
            acces.require_employee_access.side_effect = [None, HTTPException(status_code=403, detail="non")]
        with patch.object(router, "_expense_service", service), patch.object(
            router, "access_control_service", acces
        ), patch.object(router, "_require_rh_or_admin"), patch.object(
            router, "_societe_active_ou_403", return_value="co-1"
        ):
            service.get_expense.return_value = dict(NOTE)
            router.update_expense("n-1", ExpenseUpdateRequest(employee_id="e-2"), current_user=MagicMock())
        return service

    def test_vers_un_salarie_de_la_societe(self):
        service = self._appel("co-1")
        assert service.update_expense.call_args.args[0].employee_id == "e-2"

    def test_vers_un_salarie_d_une_autre_societe_refuse(self):
        with pytest.raises(HTTPException) as e:
            self._appel("co-2")
        assert e.value.status_code == 404

    def test_hors_du_perimetre_de_la_rh_refuse(self):
        with pytest.raises(HTTPException) as e:
            self._appel("co-1", acces_refuse=True)
        assert e.value.status_code == 403

"""
Service applicatif expenses (orchestration).

Délègue aux commands/queries ; pas de logique métier ici.
"""

from typing import List

from app.modules.expenses.application.commands import (
    create_expense as cmd_create_expense,
    update_expense_status as cmd_update_expense_status,
)
from app.modules.expenses.application.dto import (
    CreateExpenseInput,
    ListExpensesInput,
    UpdateExpenseStatusInput,
)
from app.modules.expenses.application.queries import (
    get_all_expenses as query_get_all_expenses,
    get_my_expenses as query_get_my_expenses,
    get_my_expenses_for_user_account as query_get_my_expenses_for_user_account,
    get_receipt_signed_url as query_get_receipt_signed_url,
    get_signed_upload_url as query_get_signed_upload_url,
    resolve_employee_id_for_expense_account as query_resolve_employee_id_for_expense_account,
)


class ExpenseApplicationService:
    """Orchestre les cas d'usage expenses (délégation aux commands/queries)."""

    def create_expense(self, input: CreateExpenseInput) -> dict:
        return cmd_create_expense(input)

    def update_expense_status(self, input: UpdateExpenseStatusInput) -> dict | None:
        return cmd_update_expense_status(input)

    def get_my_expenses(self, employee_id: str) -> List[dict]:
        return query_get_my_expenses(employee_id)

    def get_my_expenses_for_user_account(
        self, user_id: str, company_id: str | None
    ) -> List[dict]:
        return query_get_my_expenses_for_user_account(user_id, company_id)

    def resolve_employee_id_for_expense_account(
        self, user_id: str, company_id: str | None
    ) -> str | None:
        return query_resolve_employee_id_for_expense_account(user_id, company_id)

    def get_all_expenses(
        self, company_id: str, input: ListExpensesInput
    ) -> List[dict]:
        return query_get_all_expenses(company_id, input.status)

    def get_signed_upload_url(self, employee_id: str, filename: str) -> dict:
        return query_get_signed_upload_url(employee_id, filename)

    def get_receipt_signed_url(self, path: str) -> str | None:
        return query_get_receipt_signed_url(path)

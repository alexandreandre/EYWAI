"""
Queries du module expenses (lectures).

Logique migrée depuis api/routers/expenses.py — comportement identique.
"""

import os
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from app.modules.expenses.infrastructure.providers import ExpenseStorageProvider
from app.modules.expenses.infrastructure.repository import ExpenseRepository


def resolve_employee_id_for_expense_account(
    user_id: str, company_id: str | None
) -> str | None:
    """Résout employees.id pour un compte collaborateur (user_id, id, e-mail)."""
    if not company_id:
        return None
    from app.modules.employees.infrastructure.queries import (
        resolve_employee_id_for_user_account,
    )

    return resolve_employee_id_for_user_account(str(user_id), str(company_id))


def get_my_expenses_for_user_account(
    user_id: str, company_id: str | None
) -> List[dict]:
    """Notes de frais du collaborateur lié au compte auth."""
    employee_id = resolve_employee_id_for_expense_account(user_id, company_id)
    if not employee_id:
        return []
    return get_my_expenses(employee_id)


def get_my_expenses(employee_id: str) -> List[dict]:
    """
    Liste les notes de frais de l'employé (date desc), avec URLs signées pour receipt_url.
    Comportement identique à get_my_expenses du router legacy.
    """
    repo = ExpenseRepository()
    expenses_data = repo.list_by_employee_id(employee_id)
    if not expenses_data:
        return []
    paths_to_sign = [
        exp["receipt_url"] for exp in expenses_data if exp.get("receipt_url")
    ]
    if not paths_to_sign:
        return expenses_data
    storage = ExpenseStorageProvider()
    signed_urls_response = storage.create_signed_urls(paths_to_sign, 3600)
    url_map = {
        path: (url.get("signedURL") or url.get("signedUrl"))
        for path, url in zip(paths_to_sign, signed_urls_response)
        if url.get("signedURL") or url.get("signedUrl")
    }
    for exp in expenses_data:
        if exp.get("receipt_url") in url_map:
            exp["receipt_url"] = url_map[exp["receipt_url"]]
    return expenses_data


def get_all_expenses(company_id: str, status: Optional[str] = None) -> List[dict]:
    """
    Liste toutes les notes (RH) avec join employee, optionnellement filtré par status.
    Comportement identique à get_all_expenses du router legacy.
    """
    repo = ExpenseRepository()
    return repo.list_all(company_id, status)


def get_receipt_signed_url(path: str, expires_in: int = 3600) -> str | None:
    """URL signée de lecture d'un justificatif — None si le storage n'en rend pas.

    Remplace l'URL publique que le frontend fabriquait : le bucket
    expense_receipts redevient privé (audit sécurité 23/08/2026).
    """
    storage = ExpenseStorageProvider()
    resultats = storage.create_signed_urls([path], expires_in)
    for ligne in resultats or []:
        if isinstance(ligne, dict):
            url = ligne.get("signedURL") or ligne.get("signedUrl")
            if url:
                return url
    return None


def get_signed_upload_url(employee_id: str, filename: str) -> dict:
    """
    Génère une URL signée pour l'upload (path = employee_id/unique_filename).
    Comportement identique à get_upload_url du router legacy.
    """
    _root, extension = os.path.splitext(filename)
    unique_filename = f"{datetime.now().isoformat()}-{uuid4().hex}{extension}"
    path = f"{employee_id}/{unique_filename}"
    storage = ExpenseStorageProvider()
    signed_url_response = storage.create_signed_upload_url(path)
    return {
        "path": path,
        "signedURL": signed_url_response["signedUrl"],
    }

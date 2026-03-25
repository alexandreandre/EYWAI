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


def get_all_expenses(status: Optional[str] = None) -> List[dict]:
    """
    Liste toutes les notes (RH) avec join employee, optionnellement filtré par status.
    Comportement identique à get_all_expenses du router legacy.
    """
    repo = ExpenseRepository()
    return repo.list_all(status)


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

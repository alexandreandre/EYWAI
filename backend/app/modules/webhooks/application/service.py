"""Service webhooks — façade application pour routers et modules voisins."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.modules.webhooks.infrastructure.repository import webhook_repository


def list_webhooks(company_id: str) -> List[Dict[str, Any]]:
    return webhook_repository.list_by_company(company_id)


def create_webhook(
    company_id: str, data: Dict[str, Any], created_by: str
) -> Dict[str, Any]:
    return webhook_repository.create(company_id, data, created_by)


def update_webhook(
    webhook_id: str, company_id: str, patch: Dict[str, Any]
) -> Dict[str, Any]:
    return webhook_repository.update(webhook_id, company_id, patch)


def delete_webhook(webhook_id: str, company_id: str) -> bool:
    return webhook_repository.delete(webhook_id, company_id)


def send_test_webhook(webhook_id: str, company_id: str) -> Tuple[int, bool]:
    return webhook_repository.send_test(webhook_id, company_id)


def get_webhook(webhook_id: str, company_id: str) -> Optional[Dict[str, Any]]:
    return webhook_repository.get_by_id(webhook_id, company_id)


def list_webhook_logs(
    webhook_id: str, company_id: str, *, limit: int = 20
) -> List[Dict[str, Any]]:
    return webhook_repository.list_logs(webhook_id, company_id, limit=limit)


def trigger_webhook_event(
    company_id: str,
    event_type: str,
    payload: Dict[str, Any],
) -> None:
    webhook_repository.trigger_event(company_id, event_type, payload)

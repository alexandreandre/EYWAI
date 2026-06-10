"""Tests d'intégration HTTP — /api/notifications (espace collaborateur)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-notif-test"
TEST_EMPLOYEE_ID = "emp-notif-test"


def _make_employee_user(user_id: str = "user-emp-notif"):
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Test Co",
        role="collaborateur",
        is_primary=True,
    )
    return User(
        id=user_id,
        email="emp@notif.test",
        first_name="Alice",
        last_name="Test",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )


def _sample_notification(
    *,
    nid: str = "notif-1",
    ntype: str = "nouveau_document",
    is_read: bool = False,
    message: str = "Un nouveau document est disponible : « Attestation ».",
):
    return {
        "id": nid,
        "employee_id": TEST_EMPLOYEE_ID,
        "company_id": TEST_COMPANY_ID,
        "type": ntype,
        "message": message,
        "is_read": is_read,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


class TestNotificationsApiAuth:
    def test_list_returns_401_without_auth(self, client: TestClient):
        response = client.get("/api/notifications")
        assert response.status_code == 401

    def test_unread_count_returns_401_without_auth(self, client: TestClient):
        response = client.get("/api/notifications/unread-count")
        assert response.status_code == 401


class TestNotificationsApiEmployee:
    def test_list_returns_empty_when_no_employee_profile(self, client: TestClient):
        user = _make_employee_user()
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            with patch(
                "app.modules.notifications.api.router.resolve_employee_id_for_notifications",
                return_value=None,
            ):
                response = client.get("/api/notifications")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json() == []

    def test_list_returns_notifications_for_linked_employee(self, client: TestClient):
        user = _make_employee_user()
        rows = [_sample_notification(), _sample_notification(nid="notif-2", is_read=True)]
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            with (
                patch(
                    "app.modules.notifications.api.router.resolve_employee_id_for_notifications",
                    return_value=TEST_EMPLOYEE_ID,
                ),
                patch(
                    "app.modules.notifications.infrastructure.repository.notifications_repository.get_for_employee",
                    return_value=rows,
                ),
            ):
                response = client.get("/api/notifications")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["type"] == "nouveau_document"
        assert data[0]["is_read"] is False

    def test_unread_count_for_linked_employee(self, client: TestClient):
        user = _make_employee_user()
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            with (
                patch(
                    "app.modules.notifications.api.router.resolve_employee_id_for_notifications",
                    return_value=TEST_EMPLOYEE_ID,
                ),
                patch(
                    "app.modules.notifications.infrastructure.repository.notifications_repository.get_unread_count",
                    return_value=3,
                ),
            ):
                response = client.get("/api/notifications/unread-count")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json()["count"] == 3

    def test_mark_one_read_requires_employee_profile(self, client: TestClient):
        user = _make_employee_user()
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            with patch(
                "app.modules.notifications.api.router.resolve_employee_id_for_notifications",
                return_value=None,
            ):
                response = client.put("/api/notifications/notif-1/read")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 403

    def test_mark_one_read_success(self, client: TestClient):
        user = _make_employee_user()
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            with (
                patch(
                    "app.modules.notifications.api.router.resolve_employee_id_for_notifications",
                    return_value=TEST_EMPLOYEE_ID,
                ),
                patch(
                    "app.modules.notifications.infrastructure.repository.notifications_repository.mark_as_read",
                    return_value=True,
                ),
            ):
                response = client.put("/api/notifications/notif-1/read")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json()["success"] is True

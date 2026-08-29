"""
Tests d'intégration HTTP — campagnes bulletin d'option participation.

Routes sous /api/participation/campaigns* et /api/participation/me/participation-bulletins*.
Les services sont mockés pour éviter la DB réelle.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.participation.schemas.campaign_responses import (
    CampaignStats,
    ParticipationBulletinItem,
    ParticipationCampaignDetail,
    ParticipationCampaignListItem,
)


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"
TEST_EMPLOYEE_ID = "770e8400-e29b-41d4-a716-446655440002"
TEST_CAMPAIGN_ID = "880e8400-e29b-41d4-a716-446655440003"
TEST_BULLETIN_ID = "990e8400-e29b-41d4-a716-446655440004"


def _make_rh_user():
    user = MagicMock()
    user.id = TEST_USER_ID
    user.active_company_id = TEST_COMPANY_ID
    user.is_platform_admin = False
    user.has_rh_access_in_company.return_value = True
    user.get_role_in_company.return_value = "rh"
    return user


def _make_employee_user():
    user = MagicMock()
    user.id = TEST_USER_ID
    user.active_company_id = TEST_COMPANY_ID
    user.is_platform_admin = False
    user.has_rh_access_in_company.return_value = False
    return user


def _sample_campaign_detail() -> ParticipationCampaignDetail:
    now = datetime.now(timezone.utc)
    return ParticipationCampaignDetail(
        id=TEST_CAMPAIGN_ID,
        company_id=TEST_COMPANY_ID,
        simulation_id=None,
        year=2025,
        exercise_label="Participation 2025",
        status="draft",
        payroll_year=2026,
        payroll_month=5,
        sent_at=None,
        deadline_at=None,
        created_at=now,
        updated_at=now,
        stats=CampaignStats(total=2, pending=2),
    )


def _sample_bulletin(*, status: str = "sent") -> ParticipationBulletinItem:
    return ParticipationBulletinItem(
        id=TEST_BULLETIN_ID,
        campaign_id=TEST_CAMPAIGN_ID,
        employee_id=TEST_EMPLOYEE_ID,
        employee_first_name="Léo",
        employee_last_name="Cotte",
        dispositif_type="participation",
        gross_amount=3225.33,
        csg_non_deductible=93.53,
        csg_deductible=219.32,
        advance_amount=1000.0,
        advance_label="décembre 2025",
        net_amount=1912.48,
        generated_document_id=str(uuid4()),
        status=status,
        choice_type=None,
        choice_cash_amount=None,
        pee_amount=None,
        cash_amount=None,
        responded_at=None,
        deadline_at=datetime(2026, 6, 30, tzinfo=timezone.utc),
        exercise_label="Participation 2025",
        year=2025,
    )


class TestParticipationCampaignUnauthenticated:
    def test_create_campaign_returns_401(self, client: TestClient):
        response = client.post(
            "/api/participation/campaigns",
            json={"year": 2025, "exercise_label": "Participation 2025"},
        )
        assert response.status_code == 401

    def test_list_my_bulletins_returns_401(self, client: TestClient):
        response = client.get("/api/participation/me/participation-bulletins")
        assert response.status_code == 401


class TestParticipationCampaignRhRoutes:
    @pytest.fixture
    def rh_client(self, client: TestClient):
        from app.modules.participation.api.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            yield client
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.modules.participation.api.router.campaign_svc.create_campaign")
    def test_create_campaign_returns_200(self, mock_create, rh_client: TestClient):
        detail = _sample_campaign_detail()
        mock_create.return_value = (detail, 2)

        response = rh_client.post(
            "/api/participation/campaigns",
            json={
                "year": 2025,
                "exercise_label": "Participation 2025",
                "amounts": [
                    {
                        "employee_id": TEST_EMPLOYEE_ID,
                        "participation_amount": 3225.33,
                        "interessement_amount": 0,
                    }
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["bulletins_created"] == 2
        assert data["campaign"]["year"] == 2025

    @patch("app.modules.participation.api.router.campaign_svc.list_campaigns")
    def test_list_campaigns_returns_200(self, mock_list, rh_client: TestClient):
        detail = _sample_campaign_detail()
        mock_list.return_value = [
            ParticipationCampaignListItem(
                id=detail.id,
                year=detail.year,
                exercise_label=detail.exercise_label,
                status=detail.status,
                sent_at=detail.sent_at,
                deadline_at=detail.deadline_at,
                created_at=detail.created_at,
                stats=detail.stats,
            )
        ]

        response = rh_client.get("/api/participation/campaigns?year=2025")

        assert response.status_code == 200
        assert len(response.json()["campaigns"]) == 1

    @patch("app.modules.participation.api.router.campaign_svc.get_campaign_detail")
    def test_get_campaign_returns_404_when_missing(
        self, mock_get, rh_client: TestClient
    ):
        mock_get.side_effect = LookupError("Campagne introuvable")

        response = rh_client.get(f"/api/participation/campaigns/{TEST_CAMPAIGN_ID}")

        assert response.status_code == 404

    @patch("app.modules.participation.api.router.campaign_svc.publish_campaign")
    def test_publish_campaign_returns_200(self, mock_publish, rh_client: TestClient):
        detail = _sample_campaign_detail()
        detail.status = "open"
        mock_publish.return_value = detail

        response = rh_client.post(
            f"/api/participation/campaigns/{TEST_CAMPAIGN_ID}/publish"
        )

        assert response.status_code == 200
        assert response.json()["campaign"]["status"] == "open"

    @patch("app.modules.participation.api.router.campaign_svc.close_defaults")
    def test_close_defaults_returns_200(self, mock_close, rh_client: TestClient):
        detail = _sample_campaign_detail()
        detail.status = "closed"
        mock_close.return_value = (detail, 1)

        response = rh_client.post(
            f"/api/participation/campaigns/{TEST_CAMPAIGN_ID}/close-defaults"
        )

        assert response.status_code == 200
        assert "défaut PEE" in response.json()["detail"]

    @patch("app.modules.participation.api.router.campaign_svc.generate_payroll_lines")
    def test_generate_payroll_lines_returns_200(
        self, mock_generate, rh_client: TestClient
    ):
        detail = _sample_campaign_detail()
        mock_generate.return_value = (detail, 3)

        response = rh_client.post(
            f"/api/participation/campaigns/{TEST_CAMPAIGN_ID}/generate-payroll-lines",
            json={"payroll_year": 2026, "payroll_month": 5},
        )

        assert response.status_code == 200
        assert response.json()["payroll_lines_created"] == 3

    @patch("app.modules.participation.api.router.access_control_service.check_user_has_permission")
    @patch(
        "app.modules.participation.api.router.campaign_import_service.import_campaign_from_inputs"
    )
    def test_import_from_inputs_returns_200(
        self, mock_import, mock_has_permission, rh_client: TestClient
    ):
        # `check_user_has_permission` interroge la DB réelle (non pertinent
        # ici, cf. les 6 tests RH voisins de ce fichier, tous rouges en l'état
        # actuel de la branche faute de ce mock — problème préexistant, hors
        # périmètre de cette tâche).
        mock_has_permission.return_value = True
        from app.modules.participation.application.campaign_import_service import (
            ImportResult,
        )

        mock_import.return_value = ImportResult(
            campaign_id=TEST_CAMPAIGN_ID,
            bulletins=2,
            full_cash=1,
            partial_cash=0,
            full_pee=1,
            linked_inputs=3,
            skipped=False,
            dry_run=False,
            detail="2 bulletin(s) importé(s), 3 saisie(s) rattachée(s).",
        )

        response = rh_client.post(
            "/api/participation/campaigns/import-from-inputs",
            json={"year": 2025, "payroll_year": 2026, "payroll_month": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["campaign_id"] == TEST_CAMPAIGN_ID
        assert data["bulletins"] == 2
        assert data["full_pee"] == 1
        mock_import.assert_called_once()
        _, kwargs = mock_import.call_args
        assert kwargs["dry_run"] is False
        assert kwargs["force"] is False


class TestParticipationCampaignEmployeeRoutes:
    @pytest.fixture
    def employee_client(self, client: TestClient):
        from app.modules.participation.api.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_employee_user()
        try:
            yield client
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch(
        "app.modules.participation.api.router.resolve_employee_id_for_user_account",
        return_value=TEST_EMPLOYEE_ID,
    )
    @patch("app.modules.participation.api.router.campaign_svc.list_employee_bulletins")
    def test_list_my_bulletins_returns_200(
        self, mock_list, _mock_resolve, employee_client: TestClient
    ):
        mock_list.return_value = [_sample_bulletin()]

        response = employee_client.get("/api/participation/me/participation-bulletins")

        assert response.status_code == 200
        bulletins = response.json()["bulletins"]
        assert len(bulletins) == 1
        assert bulletins[0]["status"] == "sent"

    @patch(
        "app.modules.participation.api.router.resolve_employee_id_for_user_account",
        return_value=TEST_EMPLOYEE_ID,
    )
    @patch("app.modules.participation.api.router.campaign_svc.respond_to_bulletin")
    def test_respond_bulletin_returns_200(
        self, mock_respond, _mock_resolve, employee_client: TestClient
    ):
        responded = _sample_bulletin(status="responded")
        responded.choice_type = "full_pee"
        responded.pee_amount = 1912.48
        mock_respond.return_value = responded

        response = employee_client.post(
            f"/api/participation/me/participation-bulletins/{TEST_BULLETIN_ID}/respond",
            json={"choice_type": "full_pee"},
        )

        assert response.status_code == 200
        assert response.json()["choice_type"] == "full_pee"

    @patch(
        "app.modules.participation.api.router.resolve_employee_id_for_user_account",
        return_value=TEST_EMPLOYEE_ID,
    )
    @patch("app.modules.participation.api.router.campaign_svc.respond_to_bulletin")
    def test_respond_partial_cash_returns_400_on_invalid(
        self, mock_respond, _mock_resolve, employee_client: TestClient
    ):
        mock_respond.side_effect = ValueError("Montant numéraire invalide")

        response = employee_client.post(
            f"/api/participation/me/participation-bulletins/{TEST_BULLETIN_ID}/respond",
            json={"choice_type": "partial_cash", "choice_cash_amount": 5000},
        )

        assert response.status_code == 400
        assert "Montant" in response.json()["detail"]

    def test_import_from_inputs_requires_rh(self, employee_client: TestClient):
        response = employee_client.post(
            "/api/participation/campaigns/import-from-inputs",
            json={"year": 2025, "payroll_year": 2026, "payroll_month": 5},
        )
        assert response.status_code == 403

"""
Tests d'intégration HTTP des routes du module CSE.

Routes : /api/cse/* (élus, réunions, enregistrements, BDES, délégation, cycles électoraux, exports).
Utilise : client (TestClient), dependency_overrides pour get_current_user,
mocks des commandes/queries pour éviter la DB réelle.

Fixture documentée : cse_headers — en-têtes pour un utilisateur RH avec active_company_id.
À ajouter dans conftest.py si besoin de tests E2E avec JWT réel.
"""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_RH_USER_ID = "660e8400-e29b-41d4-a716-446655440001"
PREFIX = "/api/cse"


def _make_rh_user(company_id: str = TEST_COMPANY_ID, user_id: str = TEST_RH_USER_ID):
    """Utilisateur RH avec active_company_id et droits RH."""
    return User(
        id=user_id,
        email="rh@cse-test.com",
        first_name="RH",
        last_name="CSE",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=company_id,
                company_name="Test CSE Co",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=company_id,
    )


def _make_employee_user(company_id: str = TEST_COMPANY_ID):
    """Utilisateur sans droits RH (collaborateur)."""
    return User(
        id="770e8400-e29b-41d4-a716-446655440002",
        email="emp@cse-test.com",
        first_name="Emp",
        last_name="CSE",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=company_id,
                company_name="Test CSE Co",
                role="collaborateur",
                is_primary=True,
            ),
        ],
        active_company_id=company_id,
    )


def _elected_member_payload(member_id: str = "mem-1", role: str = "titulaire"):
    return {
        "id": member_id,
        "company_id": TEST_COMPANY_ID,
        "employee_id": "emp-1",
        "role": role,
        "college": "college-1",
        "start_date": "2024-01-01",
        "end_date": "2026-12-31",
        "is_active": True,
        "notes": None,
        "created_at": "2024-01-01T10:00:00",
        "updated_at": "2024-01-01T10:00:00",
        "first_name": "Jean",
        "last_name": "Dupont",
        "job_title": "Delegue",
    }


def _meeting_payload(meeting_id: str = "mtg-1", status: str = "a_venir"):
    return {
        "id": meeting_id,
        "company_id": TEST_COMPANY_ID,
        "title": "CSE ordinaire",
        "meeting_date": "2024-03-15",
        "meeting_time": None,
        "location": "Salle 1",
        "meeting_type": "ordinaire",
        "status": status,
        "agenda": None,
        "notes": None,
        "convocations_pdf_path": None,
        "created_by": TEST_RH_USER_ID,
        "created_at": "2024-03-01T10:00:00",
        "updated_at": "2024-03-01T10:00:00",
    }


def _bdes_document_payload(document_id: str = "doc-1"):
    return {
        "id": document_id,
        "company_id": TEST_COMPANY_ID,
        "title": "BDES 2024",
        "document_type": "bdes",
        "file_path": "bdes/company/doc.pdf",
        "year": 2024,
        "published_at": "2024-03-01T09:00:00",
        "published_by": TEST_RH_USER_ID,
        "is_visible_to_elected": True,
        "description": None,
        "created_at": "2024-03-01T09:00:00",
        "updated_at": "2024-03-01T09:00:00",
        "published_by_name": "RH CSE",
        "download_url": None,
    }


def _delegation_hour_payload(hour_id: str = "h-1"):
    return {
        "id": hour_id,
        "company_id": TEST_COMPANY_ID,
        "employee_id": "emp-1",
        "date": "2024-03-15",
        "duration_hours": 2.0,
        "reason": "Reunion CSE",
        "meeting_id": None,
        "created_by": TEST_RH_USER_ID,
        "created_at": "2024-03-15T10:00:00",
        "first_name": "Jean",
        "last_name": "Dupont",
    }


def _delegation_quota_payload(quota_id: str = "q-1"):
    return {
        "id": quota_id,
        "company_id": TEST_COMPANY_ID,
        "collective_agreement_id": None,
        "quota_hours_per_month": 10.0,
        "notes": None,
        "collective_agreement_name": None,
    }


def _election_cycle_payload(cycle_id: str = "cycle-1"):
    return {
        "id": cycle_id,
        "company_id": TEST_COMPANY_ID,
        "cycle_name": "2024-2026",
        "mandate_end_date": "2026-12-31",
        "election_date": None,
        "status": "in_progress",
        "results_pdf_path": None,
        "minutes_pdf_path": None,
        "notes": None,
        "created_at": "2024-01-01T10:00:00",
        "updated_at": "2024-01-01T10:00:00",
        "timeline": [],
        "days_until_mandate_end": 300,
    }


# --- Non authentifié : 401 ---


class TestCSEUnauthenticated:
    """Sans token : routes protégées renvoient 401."""

    def test_get_elected_members_401(self, client: TestClient):
        response = client.get(f"{PREFIX}/elected-members")
        assert response.status_code == 401

    def test_post_elected_member_401(self, client: TestClient):
        response = client.post(
            f"{PREFIX}/elected-members",
            json={
                "employee_id": "emp-1",
                "role": "titulaire",
                "start_date": "2024-01-01",
                "end_date": "2026-12-31",
            },
        )
        assert response.status_code == 401

    def test_get_meetings_401(self, client: TestClient):
        response = client.get(f"{PREFIX}/meetings")
        assert response.status_code == 401

    def test_get_delegation_quota_401(self, client: TestClient):
        response = client.get(f"{PREFIX}/delegation/quota")
        assert response.status_code == 401

    def test_get_election_cycles_401(self, client: TestClient):
        response = client.get(f"{PREFIX}/election-cycles")
        assert response.status_code == 401


# --- Élus CSE ---


class TestCSEElectedMembersAPI:
    """GET/POST/PUT /elected-members, GET alerts, GET me."""

    def test_get_elected_members_200(self, client: TestClient):
        from app.core.security import get_current_user

        mock_list = [_elected_member_payload()]
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.queries.get_elected_members",
                return_value=mock_list,
            ):
                response = client.get(f"{PREFIX}/elected-members")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        payload = response.json()
        assert payload[0]["id"] == mock_list[0]["id"]
        assert payload[0]["employee_id"] == mock_list[0]["employee_id"]
        assert payload[0]["role"] == mock_list[0]["role"]

    def test_get_elected_members_without_active_company_400(self, client: TestClient):
        from app.core.security import get_current_user

        user = _make_rh_user()
        user.active_company_id = None
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            response = client.get(f"{PREFIX}/elected-members")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403
        assert "accès réservé aux rh" in response.json().get("detail", "").lower()

    def test_create_elected_member_201(self, client: TestClient):
        from app.core.security import get_current_user

        created = _elected_member_payload(member_id="mem-new")
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.commands.create_elected_member",
                return_value=created,
            ):
                response = client.post(
                    f"{PREFIX}/elected-members",
                    json={
                        "employee_id": "emp-1",
                        "role": "titulaire",
                        "start_date": "2024-01-01",
                        "end_date": "2026-12-31",
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 201
        assert response.json()["id"] == "mem-new"

    def test_update_elected_member_200(self, client: TestClient):
        from app.core.security import get_current_user

        updated = _elected_member_payload(role="secretaire")
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.commands.update_elected_member",
                return_value=updated,
            ):
                response = client.put(
                    f"{PREFIX}/elected-members/mem-1",
                    json={"role": "secretaire"},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["role"] == "secretaire"

    def test_get_mandate_alerts_200(self, client: TestClient):
        from app.core.security import get_current_user

        alerts = [
            {
                "elected_member_id": "mem-1",
                "employee_id": "emp-1",
                "first_name": "Jean",
                "last_name": "Dupont",
                "role": "titulaire",
                "end_date": "2026-12-31",
                "days_remaining": 30,
                "months_remaining": 1.0,
            }
        ]
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.queries.get_mandate_alerts",
                return_value=alerts,
            ):
                response = client.get(f"{PREFIX}/elected-members/alerts")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_my_elected_status_200(self, client: TestClient):
        from app.core.security import get_current_user

        status = {"is_elected": False, "current_mandate": None, "role": None}
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.queries.get_my_elected_status",
                return_value=status,
            ):
                response = client.get(f"{PREFIX}/elected-members/me")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["is_elected"] is False

    def test_employee_cannot_create_elected_member_403(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_employee_user()
        try:
            response = client.post(
                f"{PREFIX}/elected-members",
                json={
                    "employee_id": "emp-1",
                    "role": "titulaire",
                    "start_date": "2024-01-01",
                    "end_date": "2026-12-31",
                },
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403


# --- Réunions ---


class TestCSEMeetingsAPI:
    """GET/POST/PUT meetings, participants, status."""

    def test_list_meetings_200(self, client: TestClient):
        from app.core.security import get_current_user

        meetings = [_meeting_payload()]
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.queries.get_meetings",
                return_value=meetings,
            ):
                response = client.get(f"{PREFIX}/meetings")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_create_meeting_201(self, client: TestClient):
        from app.core.security import get_current_user

        created = _meeting_payload(meeting_id="mtg-new")
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.commands.create_meeting",
                return_value=created,
            ):
                response = client.post(
                    f"{PREFIX}/meetings",
                    json={
                        "title": "CSE ordinaire",
                        "meeting_date": "2024-03-15",
                        "meeting_type": "ordinaire",
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 201
        assert response.json()["id"] == "mtg-new"

    def test_get_meeting_200(self, client: TestClient):
        from app.core.security import get_current_user

        meeting = _meeting_payload(status="terminee")
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.queries.get_meeting_by_id",
                return_value=meeting,
            ):
                response = client.get(f"{PREFIX}/meetings/mtg-1")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["id"] == "mtg-1"

    def test_update_meeting_200(self, client: TestClient):
        from app.core.security import get_current_user

        updated = _meeting_payload(status="terminee")
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.commands.update_meeting",
                return_value=updated,
            ):
                response = client.put(
                    f"{PREFIX}/meetings/mtg-1/status",
                    params={"status": "terminee"},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200

    def test_add_participants_200(self, client: TestClient):
        from app.core.security import get_current_user

        participants = [
            {
                "meeting_id": "mtg-1",
                "employee_id": "emp-1",
                "role": "participant",
                "invited_at": None,
                "confirmed_at": None,
                "attended": False,
                "first_name": "Jean",
                "last_name": "Dupont",
                "job_title": "Delegue",
            }
        ]
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.commands.add_participants",
                return_value=participants,
            ):
                response = client.post(
                    f"{PREFIX}/meetings/mtg-1/participants",
                    json={"employee_ids": ["emp-1"]},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200

    def test_remove_participant_200(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.commands.remove_participant",
                return_value=None,
            ):
                response = client.delete(f"{PREFIX}/meetings/mtg-1/participants/emp-1")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200


# --- Enregistrements ---


class TestCSERecordingAPI:
    """Start/stop recording, status, process."""

    def test_get_recording_status_200(self, client: TestClient):
        from app.core.security import get_current_user

        status = {"meeting_id": "mtg-1", "status": "not_started"}
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.queries.get_recording_status",
                return_value=status,
            ):
                response = client.get(f"{PREFIX}/meetings/mtg-1/recording/status")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["status"] == "not_started"

    def test_start_recording_200(self, client: TestClient):
        from app.core.security import get_current_user

        status = {"meeting_id": "mtg-1", "status": "in_progress"}
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.commands.start_recording",
                return_value=status,
            ):
                response = client.post(
                    f"{PREFIX}/meetings/mtg-1/recording/start",
                    json={
                        "consents": [{"employee_id": "emp-1", "consent_given": True}]
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200

    def test_stop_recording_200(self, client: TestClient):
        from app.core.security import get_current_user

        status = {"meeting_id": "mtg-1", "status": "completed"}
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.commands.stop_recording",
                return_value=status,
            ):
                response = client.post(f"{PREFIX}/meetings/mtg-1/recording/stop")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200

    def test_process_recording_200(self, client: TestClient):
        from app.core.security import get_current_user

        result = {"transcription": "...", "summary": "..."}
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.commands.process_recording",
                return_value=result,
            ):
                response = client.post(f"{PREFIX}/meetings/mtg-1/recording/process")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200


# --- PV et BDES ---


class TestCSEMinutesAndBDESAPI:
    """GET minutes, GET/POST bdes-documents, GET download."""

    def test_get_minutes_200(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.get_meeting_minutes_path_or_raise",
                return_value="path/to/pv.pdf",
            ):
                response = client.get(f"{PREFIX}/meetings/mtg-1/minutes")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["pdf_path"] == "path/to/pv.pdf"

    def test_list_bdes_documents_200(self, client: TestClient):
        from app.core.security import get_current_user

        docs = [_bdes_document_payload()]
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.queries.get_bdes_documents",
                return_value=docs,
            ):
                response = client.get(f"{PREFIX}/bdes-documents")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_upload_bdes_document_201(self, client: TestClient):
        from app.core.security import get_current_user

        created = _bdes_document_payload(document_id="doc-new")
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.commands.upload_bdes_document",
                return_value=created,
            ):
                response = client.post(
                    f"{PREFIX}/bdes-documents",
                    data={
                        "title": "BDES 2024",
                        "document_type": "bdes",
                        "year": 2024,
                    },
                    files={"file": ("bdes.pdf", b"pdf-content", "application/pdf")},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 201
        assert response.json()["id"] == "doc-new"

    def test_download_bdes_document_200(self, client: TestClient):
        from app.core.security import get_current_user

        doc = MagicMock()
        doc.file_path = "bdes/co-1/doc.pdf"
        doc.is_visible_to_elected = True
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.queries.get_bdes_document_by_id",
                return_value=doc,
            ):
                response = client.get(f"{PREFIX}/bdes-documents/doc-1/download")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert "download_url" in response.json()


# --- Délégation ---


class TestCSEDelegationAPI:
    """GET quota, GET hours, POST hours, GET summary, GET quotas."""

    def test_get_delegation_quota_200(self, client: TestClient):
        from app.core.security import get_current_user

        quota = _delegation_quota_payload()
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.queries.get_delegation_quota",
                return_value=quota,
            ):
                response = client.get(f"{PREFIX}/delegation/quota")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["quota_hours_per_month"] == 10.0

    def test_get_delegation_hours_200(self, client: TestClient):
        from app.core.security import get_current_user

        hours = [_delegation_hour_payload()]
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.queries.get_delegation_hours",
                return_value=hours,
            ):
                response = client.get(f"{PREFIX}/delegation/hours")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_create_delegation_hour_201(self, client: TestClient):
        from app.core.security import get_current_user

        created = _delegation_hour_payload(hour_id="h-new")
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.commands.create_delegation_hour",
                return_value=created,
            ):
                response = client.post(
                    f"{PREFIX}/delegation/hours",
                    json={
                        "date": "2024-03-15",
                        "duration_hours": 2.0,
                        "reason": "Réunion CSE",
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 201

    def test_get_delegation_summary_200(self, client: TestClient):
        from app.core.security import get_current_user

        summary = [
            {
                "employee_id": "emp-1",
                "first_name": "Jean",
                "last_name": "Dupont",
                "quota_hours_per_month": 10.0,
                "consumed_hours": 5.0,
                "remaining_hours": 5.0,
                "period_start": "2024-03-01",
                "period_end": "2024-03-31",
            }
        ]
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.queries.get_delegation_summary",
                return_value=summary,
            ):
                response = client.get(
                    f"{PREFIX}/delegation/summary",
                    params={
                        "period_start": "2024-03-01",
                        "period_end": "2024-03-31",
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200

    def test_list_delegation_quotas_200(self, client: TestClient):
        from app.core.security import get_current_user

        quotas = [_delegation_quota_payload()]
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.queries.list_delegation_quotas",
                return_value=quotas,
            ):
                response = client.get(f"{PREFIX}/delegation/quotas")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200


# --- Calendrier électoral ---


class TestCSEElectionCyclesAPI:
    """GET/POST election-cycles, GET alerts, GET cycle by id."""

    def test_list_election_cycles_200(self, client: TestClient):
        from app.core.security import get_current_user

        cycles = [_election_cycle_payload()]
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.queries.get_election_cycles",
                return_value=cycles,
            ):
                response = client.get(f"{PREFIX}/election-cycles")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_create_election_cycle_201(self, client: TestClient):
        from app.core.security import get_current_user

        created = _election_cycle_payload(cycle_id="cycle-new")
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.commands.create_election_cycle",
                return_value=created,
            ):
                response = client.post(
                    f"{PREFIX}/election-cycles",
                    json={
                        "cycle_name": "2024-2026",
                        "mandate_end_date": "2024-12-31",
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 201
        assert response.json()["cycle_name"] == "2024-2026"

    def test_get_election_alerts_200(self, client: TestClient):
        from app.core.security import get_current_user

        alerts = [
            {
                "cycle_id": "cycle-1",
                "cycle_name": "2024-2026",
                "mandate_end_date": "2026-12-31",
                "days_remaining": 90,
                "alert_level": "warning",
                "message": "Election a preparer",
            }
        ]
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.queries.get_election_alerts",
                return_value=alerts,
            ):
                response = client.get(f"{PREFIX}/election-cycles/alerts")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200

    def test_get_election_cycle_by_id_200(self, client: TestClient):
        from app.core.security import get_current_user

        cycle = _election_cycle_payload()
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.queries.get_election_cycle_by_id",
                return_value=cycle,
            ):
                response = client.get(f"{PREFIX}/election-cycles/cycle-1")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["id"] == "cycle-1"


# --- Exports ---


class TestCSEExportsAPI:
    """GET exports/elected-members, delegation-hours, meetings-history, minutes-annual, election-calendar."""

    def test_export_elected_members_200(self, client: TestClient):
        from app.core.security import get_current_user

        out = MagicMock()
        out.content = b"xlsx"
        out.media_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        out.filename = "base_elus_cse.xlsx"
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.export_elected_members_file",
                return_value=out,
            ):
                response = client.get(f"{PREFIX}/exports/elected-members")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.content == b"xlsx"
        assert "base_elus_cse" in response.headers.get("Content-Disposition", "")

    def test_export_delegation_hours_200(self, client: TestClient):
        from app.core.security import get_current_user

        out = MagicMock()
        out.content = b"xlsx"
        out.media_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        out.filename = "heures_delegation_cse.xlsx"
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.export_delegation_hours_file",
                return_value=out,
            ):
                response = client.get(f"{PREFIX}/exports/delegation-hours")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200

    def test_export_meetings_history_200(self, client: TestClient):
        from app.core.security import get_current_user

        out = MagicMock()
        out.content = b"xlsx"
        out.media_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        out.filename = "historique_reunions_cse.xlsx"
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.export_meetings_history_file",
                return_value=out,
            ):
                response = client.get(f"{PREFIX}/exports/meetings-history")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200

    def test_export_minutes_annual_200(self, client: TestClient):
        from app.core.security import get_current_user

        out = MagicMock()
        out.content = b"%PDF"
        out.media_type = "application/pdf"
        out.filename = "pv_annuels_2024.pdf"
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.export_minutes_annual_file",
                return_value=out,
            ):
                response = client.get(
                    f"{PREFIX}/exports/minutes-annual",
                    params={"year": 2024},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.content == b"%PDF"

    def test_export_election_calendar_200(self, client: TestClient):
        from app.core.security import get_current_user

        out = MagicMock()
        out.content = b"%PDF"
        out.media_type = "application/pdf"
        out.filename = "calendrier_electoral.pdf"
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.cse.api.router.export_election_calendar_file",
                return_value=out,
            ):
                response = client.get(f"{PREFIX}/exports/election-calendar")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200

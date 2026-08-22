"""
Task 5 (lien d'activation) : chaîne complète invite → verify → complete.

Un seul état en mémoire traverse tout le flux, par les VRAIS points
d'entrée HTTP et le VRAI sender (SMTP capturé — aucune connexion réseau).
Le jeton utilisé aux étapes publiques est EXTRAIT DE L'E-MAIL réellement
construit, jamais fabriqué par le test.

Critère d'acceptation non négociable : après activation, GET
/api/me/payslips répond 200 pour ce compte — via la VRAIE résolution
resolve_employee_id_for_user_account (branche employees.user_id).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.message import Message
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.activation.application import commands, queries
from app.modules.platform_settings.domain.value_objects import ResolvedEmailConfig
from app.modules.users.schemas.responses import CompanyAccess, User
from app.shared.infrastructure.email.smtp_sender import SmtpMailSender

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
RH_USER_ID = "660e8400-e29b-41d4-a716-446655440001"
EMPLOYEE_ID = "770e8400-e29b-41d4-a716-446655440099"
AUTH_UID = "990e8400-e29b-41d4-a716-446655440555"

INVITE_URL = f"/api/employees/{EMPLOYEE_ID}/invitation"


# ----- Faux dépôts / providers à état partagé -----


class FakeTokenRepository:
    def __init__(self):
        self.rows: list[dict] = []

    def invalidate_pending(self, employee_id: str, now_iso: str) -> None:
        for row in self.rows:
            if (
                row["employee_id"] == str(employee_id)
                and not row["used_at"]
                and not row["invalidated_at"]
            ):
                row["invalidated_at"] = now_iso

    def create(self, **kwargs) -> None:
        self.rows.append(
            {
                "id": f"tok-{len(self.rows) + 1}",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "used_at": None,
                "invalidated_at": None,
                **kwargs,
            }
        )

    def get_by_hash(self, token_hash: str):
        for row in self.rows:
            if row["token_hash"] == token_hash:
                return row
        return None

    def mark_used(self, token_id: str, now_iso: str) -> None:
        for row in self.rows:
            if row["id"] == str(token_id):
                row["used_at"] = now_iso

    def get_latest_for_employee(self, employee_id: str):
        rows = [r for r in self.rows if r["employee_id"] == str(employee_id)]
        return rows[-1] if rows else None


class FakeEmployeesTableQuery:
    """Réponses de supabase.table('employees') pour la VRAIE résolution."""

    def __init__(self, employee: dict):
        self._employee = employee
        self._filters: dict = {}

    def select(self, *args, **kwargs):
        return self

    def eq(self, column: str, value):
        self._filters[column] = str(value)
        return self

    def maybe_single(self):
        return self

    def execute(self):
        emp = self._employee
        if self._filters.get("company_id") != str(emp["company_id"]):
            return SimpleNamespace(data=None)
        if "user_id" in self._filters:
            match = emp.get("user_id") and str(emp["user_id"]) == self._filters["user_id"]
        elif "id" in self._filters:
            match = str(emp["id"]) == self._filters["id"]
        else:
            match = False
        return SimpleNamespace(data={"id": emp["id"]} if match else None)


class FakeResolutionSupabase:
    def __init__(self, employee: dict):
        self._employee = employee

    def table(self, name: str):
        assert name == "employees"
        return FakeEmployeesTableQuery(self._employee)

    # Pas d'attribut auth : la branche « même e-mail » échoue proprement
    # (try/except dans _resolve_employee_id_by_auth_email).


def _rh_user() -> User:
    return User(
        id=RH_USER_ID,
        email="rh@entreprise.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=COMPANY_ID,
                company_name="Entreprise Test",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=COMPANY_ID,
    )


def _activated_employee_user() -> User:
    """Le compte créé par l'activation (id = uid auth, rôle collaborateur)."""
    return User(
        id=AUTH_UID,
        email="jean.dupont@exemple.fr",
        first_name="Jean",
        last_name="Dupont",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=COMPANY_ID,
                company_name="Entreprise Test",
                role="collaborateur",
                is_primary=True,
            ),
        ],
        active_company_id=COMPANY_ID,
    )


def _smtp_config() -> ResolvedEmailConfig:
    return ResolvedEmailConfig(
        smtp_host="smtp.exemple.fr",
        smtp_port=587,
        smtp_user="expediteur@exemple.fr",
        smtp_password="secret-smtp-de-test",
        smtp_security="starttls",
        from_email="noreply@exemple.fr",
        from_name="EYWAI",
        reply_to=None,
        support_recipients=("contact@exemple.fr",),
        frontend_url="https://app.exemple.fr",
        source="environment",
    )


def _extract_token(message: Message) -> str:
    for part in message.walk():
        if part.get_content_type() == "text/plain":
            text = part.get_payload(decode=True).decode("utf-8")
            found = re.search(r"/activation\?token=([A-Za-z0-9_\-]+)", text)
            assert found, "lien d'activation absent de l'e-mail"
            return found.group(1)
    raise AssertionError("partie texte absente de l'e-mail")


@pytest.fixture
def chaine(monkeypatch):
    """Monte tout le décor partagé et rend (client-état) au test."""
    employee = {
        "id": EMPLOYEE_ID,
        "company_id": COMPANY_ID,
        "first_name": "Jean",
        "last_name": "Dupont",
        "email": "jean.dupont@exemple.fr",
        "employment_status": "actif",
        "user_id": None,
        "job_title": "Technicien",
    }
    repo = FakeTokenRepository()
    messages: list[Message] = []

    monkeypatch.setattr(commands, "_token_repository", repo)
    monkeypatch.setattr(queries, "_token_repository", repo)

    prov = commands.providers  # module partagé commands/queries
    monkeypatch.setattr(
        prov, "get_employee_for_activation", lambda _id: dict(employee)
    )
    monkeypatch.setattr(prov, "get_company_name", lambda _id: "Entreprise Test")
    monkeypatch.setattr(prov, "auth_email_deja_pris", lambda _e, exclude_user_id=None: False)
    monkeypatch.setattr(prov, "create_auth_user", lambda _e, _p: AUTH_UID)
    monkeypatch.setattr(
        prov,
        "update_auth_user_password",
        MagicMock(side_effect=AssertionError("compte existant inattendu")),
    )
    monkeypatch.setattr(prov, "ensure_profile", MagicMock())
    monkeypatch.setattr(prov, "ensure_company_access", MagicMock())
    monkeypatch.setattr(
        prov,
        "link_employee_to_user",
        lambda _eid, uid: employee.update({"user_id": str(uid)}),
    )

    server = MagicMock()
    server.send_message.side_effect = lambda msg: messages.append(msg)
    context = MagicMock()
    context.__enter__ = MagicMock(return_value=server)
    context.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(SmtpMailSender, "_connect", lambda self, cfg: context)
    monkeypatch.setattr(
        "app.shared.infrastructure.email.smtp_sender.get_resolved_email_config",
        _smtp_config,
    )
    monkeypatch.setattr("app.core.settings.EMAIL_FORCE_REDIRECT_TO", None)
    monkeypatch.setattr("app.core.settings.ACTIVATION_EMAIL_ALLOWLIST", "")

    yield SimpleNamespace(employee=employee, repo=repo, messages=messages)
    app.dependency_overrides.pop(get_current_user, None)


class TestChaineComplete:
    def test_invite_verify_complete_puis_mes_bulletins(
        self, client: TestClient, chaine
    ):
        # 1) La RH invite : jeton haché stocké, e-mail réellement construit.
        app.dependency_overrides[get_current_user] = _rh_user
        invited = client.post(INVITE_URL)
        assert invited.status_code == 200, invited.text
        assert len(chaine.repo.rows) == 1
        assert len(chaine.messages) == 1
        raw_token = _extract_token(chaine.messages[0])
        # Le jeton en clair n'est pas en base.
        assert raw_token != chaine.repo.rows[0]["token_hash"]

        # 2) verify : accueil personnalisé.
        verified = client.post(
            "/api/activation/verify", json={"token": raw_token}
        )
        assert verified.status_code == 200, verified.text
        assert verified.json() == {
            "prenom": "Jean",
            "societe": "Entreprise Test",
        }

        # 3) complete : compte créé + fiche liée + jeton consommé.
        completed = client.post(
            "/api/activation/complete",
            json={"token": raw_token, "password": "MotDePasse!2026"},
        )
        assert completed.status_code == 200, completed.text
        assert chaine.employee["user_id"] == AUTH_UID
        assert chaine.repo.rows[0]["used_at"] is not None

        # 4) Second complete avec le MÊME jeton → 400 générique.
        again = client.post(
            "/api/activation/complete",
            json={"token": raw_token, "password": "MotDePasse!2026"},
        )
        assert again.status_code == 400
        assert again.json()["detail"] == "Lien invalide ou expiré"

        # 5) Critère d'acceptation : GET /api/me/payslips répond 200 (vide)
        # pour le compte activé, via la VRAIE résolution employees.user_id.
        app.dependency_overrides[get_current_user] = _activated_employee_user
        fake_supabase = FakeResolutionSupabase(chaine.employee)
        with (
            patch(
                "app.modules.employees.infrastructure.queries.supabase",
                fake_supabase,
            ),
            patch(
                "app.modules.payslips.application.queries._get_my_payslips",
                MagicMock(return_value=[]),
            ) as mock_list,
        ):
            mine = client.get("/api/me/payslips")
        assert mine.status_code == 200, mine.text
        assert mine.json() == []
        # La fiche a bien été résolue via user_id → employees.id.
        mock_list.assert_called_once_with(EMPLOYEE_ID)

        # 6) L'état RH passe à « activé ».
        app.dependency_overrides[get_current_user] = _rh_user
        status = client.get(INVITE_URL)
        assert status.status_code == 200
        assert status.json()["status"] == "active"

    def test_avant_activation_pas_de_fiche_resolue(
        self, client: TestClient, chaine
    ):
        """Contre-épreuve : sans activation, la résolution ne trouve rien."""
        app.dependency_overrides[get_current_user] = _activated_employee_user
        fake_supabase = FakeResolutionSupabase(chaine.employee)
        with (
            patch(
                "app.modules.employees.infrastructure.queries.supabase",
                fake_supabase,
            ),
            patch(
                "app.modules.payslips.application.queries._get_my_payslips",
                MagicMock(return_value=[]),
            ) as mock_list,
        ):
            mine = client.get("/api/me/payslips")
        assert mine.status_code == 200
        assert mine.json() == []
        mock_list.assert_not_called()

    def test_jeton_expire_refuse(self, client: TestClient, chaine):
        app.dependency_overrides[get_current_user] = _rh_user
        assert client.post(INVITE_URL).status_code == 200
        raw_token = _extract_token(chaine.messages[0])
        # Le temps passe : 7 jours et une heure.
        chaine.repo.rows[0]["expires_at"] = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).isoformat()

        verified = client.post(
            "/api/activation/verify", json={"token": raw_token}
        )
        assert verified.status_code == 400
        assert verified.json()["detail"] == "Lien invalide ou expiré"
        completed = client.post(
            "/api/activation/complete",
            json={"token": raw_token, "password": "MotDePasse!2026"},
        )
        assert completed.status_code == 400
        assert chaine.employee["user_id"] is None

    def test_reenvoi_invalide_l_ancien_jeton(self, client: TestClient, chaine):
        app.dependency_overrides[get_current_user] = _rh_user
        assert client.post(INVITE_URL).status_code == 200
        assert client.post(INVITE_URL).status_code == 200
        assert len(chaine.messages) == 2
        ancien = _extract_token(chaine.messages[0])
        nouveau = _extract_token(chaine.messages[1])
        assert ancien != nouveau

        # L'ancien est mort, le nouveau vit.
        assert (
            client.post(
                "/api/activation/verify", json={"token": ancien}
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/activation/verify", json={"token": nouveau}
            ).status_code
            == 200
        )

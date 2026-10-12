"""« Envoyer sur l'espace Documents du collaborateur » : la publication répond.

Relevé du 12/10/2026 (vidéo H) : POST `/documents/publish` répondait 500
« Internal Server Error », deux fois de suite. La commande rendait des UUID là où
le modèle de réponse attend des chaînes : la réponse ne se construisait pas,
après que les documents avaient été copiés dans l'espace du salarié. Et rien ne
marquait le document du départ comme publié : la liste ne disait pas « Publié ».
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

pytestmark = pytest.mark.unit

_SOCIETE = "aaaaaaaa-1111-1111-1111-111111111111"
_DEPART = "bbbbbbbb-2222-2222-2222-222222222222"
_SALARIE = "cccccccc-3333-3333-3333-333333333333"
_DOCUMENT = "dddddddd-4444-4444-4444-444444444444"
_DOCUMENT_SALARIE = "eeeeeeee-5555-5555-5555-555555555555"
_RH = "ffffffff-6666-6666-6666-666666666666"
_COMMANDES = "app.modules.employee_exits.application.commands"


def _rh() -> User:
    return User(
        id=_RH,
        email="rh@societe-a.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(company_id=_SOCIETE, company_name="Société A", role="rh", is_primary=True)
        ],
        active_company_id=_SOCIETE,
    )


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = _rh
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def depart():
    """Un départ avec un certificat généré, et ses écritures observées."""
    documents = MagicMock()
    documents.list_by_exit.return_value = [
        {
            "id": _DOCUMENT,
            "document_type": "certificat_travail",
            "document_category": "generated",
            "filename": "certificat_travail.pdf",
            "storage_path": f"exits/{_DEPART}/certificat_travail.pdf",
            "mime_type": "application/pdf",
            "file_size_bytes": 1234,
        }
    ]
    departs = MagicMock()
    departs.get_with_employee.return_value = {"id": _DEPART, "employee_id": _SALARIE}
    stockage = MagicMock()
    stockage.download.return_value = b"%PDF-1.4"
    stockage.create_signed_url.return_value = "https://stockage/signe"
    with patch(f"{_COMMANDES}.ExitDocumentRepository", return_value=documents), patch(
        f"{_COMMANDES}.EmployeeExitRepository", return_value=departs
    ), patch(f"{_COMMANDES}.get_exit_storage_provider", return_value=stockage), patch(
        f"{_COMMANDES}.get_employee_document_by_source_exit_document", return_value=None
    ), patch(
        f"{_COMMANDES}.insert_employee_document", return_value={"id": _DOCUMENT_SALARIE}
    ), patch(f"{_COMMANDES}.insert_exit_document_publication"), patch(
        f"{_COMMANDES}.notify_employee_new_document"
    ), patch(f"{_COMMANDES}.supabase", MagicMock()):
        yield documents


def test_publier_repond_200_avec_le_document_publie(client, depart):
    reponse = client.post(
        f"/api/employee-exits/{_DEPART}/documents/publish",
        json={"document_ids": None, "force_update": False},
    )
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["success"] is True
    assert corps["total_published"] == 1
    assert corps["exit_id"] == _DEPART
    assert corps["employee_id"] == _SALARIE
    assert corps["documents"][0]["exit_document_id"] == _DOCUMENT
    assert corps["documents"][0]["employee_document_id"] == _DOCUMENT_SALARIE
    assert corps["documents"][0]["status"] == "published"


def test_le_document_du_depart_est_marque_publie(client, depart):
    """Sans cette écriture, la liste des documents du départ ne disait jamais
    « Publié » (seule la dépublication touchait `published_to_employee`)."""
    client.post(
        f"/api/employee-exits/{_DEPART}/documents/publish",
        json={"document_ids": None, "force_update": False},
    )
    marques = [
        appel.args[3]
        for appel in depart.update.call_args_list
        if appel.args[0] == _DOCUMENT and appel.args[3].get("published_to_employee") is True
    ]
    assert marques, "le document du départ n'est pas marqué publié"
    assert marques[0]["published_by"] == _RH
    assert marques[0]["published_at"]

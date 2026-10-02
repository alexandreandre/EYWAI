"""POST /api/client-errors : authentifié, assaini, débit limité, sans table."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.client_errors.application import commands as cmds
from app.modules.client_errors.domain.rules import assainir_journal
from app.modules.users.schemas.responses import CompanyAccess, User

pytestmark = pytest.mark.unit


def test_assainir_retire_nom_rib_et_pdf_et_tronque_la_pile():
    propre = assainir_journal(
        {
            "ecran": "creation-salarie",
            "action": "enregistrer",
            "message": "Nom : Jeanne Essai IBAN FR7630006000011234567890189 fichier contrat.pdf",
            "pile": "\n".join(f"ligne {i}" for i in range(40)),
            "last_name": "Essai",
            "pdf": "AAAA",
        }
    )
    assert set(propre) == {"ecran", "action", "message", "pile"}
    assert "Jeanne" not in propre["message"]
    assert "FR76" not in propre["message"]
    assert "contrat.pdf" not in propre["message"].lower()
    assert propre["pile"].count("\n") < 20
    assert "last_name" not in propre


def test_assainir_retire_un_nom_en_majuscules_et_les_montants():
    propre = assainir_journal(
        {
            "ecran": "bulletin Jeanne ESSAI",
            "action": "ouvrir ESSAI Jeanne",
            "message": "Salarié Jeanne ESSAI : net 1 842,15 € au lieu de 2010.40",
            "pile": "TypeError: Cannot read properties of undefined (reading 'x')\n at f (app.js:12:345)",
        }
    )
    tout = " ".join(propre.values())
    assert "ESSAI" not in tout
    assert "Jeanne" not in tout
    assert "842" not in tout
    assert "2010.40" not in tout
    # Une pile technique reste lisible.
    assert "TypeError: Cannot read properties of undefined" in propre["pile"]
    assert "app.js:12:345" in propre["pile"]


def _utilisateur():
    return User(
        id="33333333-3333-3333-3333-333333333333",
        email="rh@example.com",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id="22222222-2222-2222-2222-222222222222",
                company_name="Demo",
                role="rh",
                is_primary=True,
            )
        ],
        active_company_id="22222222-2222-2222-2222-222222222222",
    )


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = _utilisateur
    cmds._attempts.clear()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        cmds._attempts.clear()


def test_un_signalement_authentifie_est_journalise(client, caplog):
    with caplog.at_level("WARNING", logger="modules.client_errors"):
        reponse = client.post(
            "/api/client-errors",
            json={
                "ecran": "creation-salarie",
                "action": "enregistrer",
                "message": "validation inattendue last_name",
                "pile": "TypeError: x",
            },
        )
    assert reponse.status_code == 204
    assert "erreur-ecran" in caplog.text
    assert "creation-salarie" in caplog.text
    assert "Jeanne" not in caplog.text


def test_sans_jeton_le_journal_est_refuse():
    app.dependency_overrides.pop(get_current_user, None)
    reponse = TestClient(app).post("/api/client-errors", json={"ecran": "x", "action": "y"})
    assert reponse.status_code in (401, 403)


def test_le_debit_limite_renvoie_429(client):
    with patch.object(cmds.time, "monotonic", return_value=1000.0):
        for _ in range(cmds.DEBIT_MAX):
            assert client.post("/api/client-errors", json={"ecran": "a", "action": "b"}).status_code == 204
        trop = client.post("/api/client-errors", json={"ecran": "a", "action": "b"})
    assert trop.status_code == 429
    assert "Trop de signalements" in trop.json()["detail"]

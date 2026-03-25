"""
Tests d'intégration HTTP des routes du module contract_parser.

Routes : POST /api/contract-parser/extract-from-pdf,
         POST /api/contract-parser/extract-rib-from-pdf,
         POST /api/contract-parser/extract-questionnaire-from-pdf.
Utilise : client (TestClient), dependency_overrides pour get_current_user.
Pour des réponses déterministes sans appel LLM/PDF réel, les commandes sont mockées.
"""

from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.contract_parser.application.dto import ExtractionResultDto
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _make_contract_parser_user(
    company_id: str = TEST_COMPANY_ID, user_id: str = TEST_USER_ID
):
    """Utilisateur de test pour les routes contract_parser (auth requise)."""
    return User(
        id=user_id,
        email="user@contract-parser-test.com",
        first_name="Test",
        last_name="ContractParser",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=company_id,
                company_name="Test Co",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=company_id,
    )


def _pdf_file(content: bytes = b"%PDF-1.4 minimal", filename: str = "document.pdf"):
    """Fichier upload simulé (PDF)."""
    return (filename, BytesIO(content), "application/pdf")


# ---------------------------------------------------------------------------
# Sans authentification → 401
# ---------------------------------------------------------------------------


class TestContractParserUnauthenticated:
    """Sans token : toutes les routes POST renvoient 401."""

    def test_extract_from_pdf_returns_401_without_auth(self, client: TestClient):
        """POST /api/contract-parser/extract-from-pdf sans token → 401."""
        response = client.post(
            "/api/contract-parser/extract-from-pdf",
            files={"file": _pdf_file()},
        )
        assert response.status_code == 401

    def test_extract_rib_from_pdf_returns_401_without_auth(self, client: TestClient):
        """POST /api/contract-parser/extract-rib-from-pdf sans token → 401."""
        response = client.post(
            "/api/contract-parser/extract-rib-from-pdf",
            files={"file": _pdf_file()},
        )
        assert response.status_code == 401

    def test_extract_questionnaire_from_pdf_returns_401_without_auth(
        self, client: TestClient
    ):
        """POST /api/contract-parser/extract-questionnaire-from-pdf sans token → 401."""
        response = client.post(
            "/api/contract-parser/extract-questionnaire-from-pdf",
            files={"file": _pdf_file()},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Validation entrée : fichier non PDF ou vide → 400
# ---------------------------------------------------------------------------


class TestContractParserValidation:
    """Validation du fichier : format PDF requis, fichier non vide."""

    def test_extract_from_pdf_rejects_non_pdf_with_auth(self, client: TestClient):
        """Avec auth : fichier .txt → 400."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: (
            _make_contract_parser_user()
        )
        try:
            response = client.post(
                "/api/contract-parser/extract-from-pdf",
                files={"file": ("document.txt", BytesIO(b"not a pdf"), "text/plain")},
            )
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data
            assert "PDF" in data["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_extract_from_pdf_rejects_empty_file_with_auth(self, client: TestClient):
        """Avec auth : fichier PDF vide → 400."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: (
            _make_contract_parser_user()
        )
        try:
            response = client.post(
                "/api/contract-parser/extract-from-pdf",
                files={"file": _pdf_file(content=b"")},
            )
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data
            assert "vide" in data["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_extract_rib_rejects_non_pdf_with_auth(self, client: TestClient):
        """extract-rib : fichier non PDF → 400."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: (
            _make_contract_parser_user()
        )
        try:
            response = client.post(
                "/api/contract-parser/extract-rib-from-pdf",
                files={"file": ("rib.png", BytesIO(b"fake"), "image/png")},
            )
            assert response.status_code == 400
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_extract_questionnaire_rejects_empty_pdf_with_auth(
        self, client: TestClient
    ):
        """extract-questionnaire : PDF vide → 400."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: (
            _make_contract_parser_user()
        )
        try:
            response = client.post(
                "/api/contract-parser/extract-questionnaire-from-pdf",
                files={"file": _pdf_file(content=b"")},
            )
            assert response.status_code == 400
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Avec auth + commande mockée → 200 et structure de réponse
# ---------------------------------------------------------------------------


class TestContractParserExtractFromPdfWithAuth:
    """POST /api/contract-parser/extract-from-pdf avec auth et commande mockée."""

    def test_returns_200_and_extraction_structure(self, client: TestClient):
        """Réponse 200 avec extracted_data, confidence, warnings."""
        from app.core.security import get_current_user

        fake_result = ExtractionResultDto(
            extracted_data={
                "first_name": "Jean",
                "last_name": "Dupont",
                "hire_date": "2024-01-15",
            },
            confidence="high",
            warnings=[],
        )

        app.dependency_overrides[get_current_user] = lambda: (
            _make_contract_parser_user()
        )
        try:
            with patch(
                "app.modules.contract_parser.api.router.commands.extract_contract_from_pdf",
                return_value=fake_result,
            ):
                response = client.post(
                    "/api/contract-parser/extract-from-pdf",
                    files={"file": _pdf_file(b"%PDF-1.4 content")},
                )
            assert response.status_code == 200
            data = response.json()
            assert "extracted_data" in data
            assert data["extracted_data"]["first_name"] == "Jean"
            assert data["extracted_data"]["last_name"] == "Dupont"
            assert data["confidence"] == "high"
            assert data["warnings"] == []
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestContractParserExtractRibWithAuth:
    """POST /api/contract-parser/extract-rib-from-pdf avec auth et mock."""

    def test_returns_200_and_rib_structure(self, client: TestClient):
        """Réponse 200 avec champs RIB (iban, bic)."""
        from app.core.security import get_current_user

        fake_result = ExtractionResultDto(
            extracted_data={
                "iban": "FR7612345678901234567890123",
                "bic": "SOGEFRPP",
            },
            confidence="high",
            warnings=[],
        )

        app.dependency_overrides[get_current_user] = lambda: (
            _make_contract_parser_user()
        )
        try:
            with patch(
                "app.modules.contract_parser.api.router.commands.extract_rib_from_pdf",
                return_value=fake_result,
            ):
                response = client.post(
                    "/api/contract-parser/extract-rib-from-pdf",
                    files={"file": _pdf_file()},
                )
            assert response.status_code == 200
            data = response.json()
            assert data["extracted_data"]["iban"] == "FR7612345678901234567890123"
            assert data["extracted_data"]["bic"] == "SOGEFRPP"
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestContractParserExtractQuestionnaireWithAuth:
    """POST /api/contract-parser/extract-questionnaire-from-pdf avec auth et mock."""

    def test_returns_200_and_questionnaire_structure(self, client: TestClient):
        """Réponse 200 avec structure questionnaire."""
        from app.core.security import get_current_user

        fake_result = ExtractionResultDto(
            extracted_data={
                "first_name": "Marie",
                "last_name": "Martin",
                "job_title": "Développeur",
            },
            confidence="medium",
            warnings=["Salaire non renseigné"],
        )

        app.dependency_overrides[get_current_user] = lambda: (
            _make_contract_parser_user()
        )
        try:
            with patch(
                "app.modules.contract_parser.api.router.commands.extract_questionnaire_from_pdf",
                return_value=fake_result,
            ):
                response = client.post(
                    "/api/contract-parser/extract-questionnaire-from-pdf",
                    files={"file": _pdf_file()},
                )
            assert response.status_code == 200
            data = response.json()
            assert data["extracted_data"]["first_name"] == "Marie"
            assert data["warnings"] == ["Salaire non renseigné"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)

"""
Tests de wiring (injection de dépendances et flux bout en bout) du module contract_parser.

Vérifie que :
- get_current_user est bien injecté et que les routes protégées reçoivent l'utilisateur.
- Le flux route → commande (mockée ou réelle) → réponse fonctionne.
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


def _make_user(company_id: str = TEST_COMPANY_ID, user_id: str = TEST_USER_ID) -> User:
    """Utilisateur de test pour get_current_user override."""
    return User(
        id=user_id,
        email="wiring@contract-parser-test.com",
        first_name="Wiring",
        last_name="Test",
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


def _pdf_file(content: bytes = b"%PDF-1.4 minimal"):
    """Fichier PDF minimal pour upload."""
    return ("document.pdf", BytesIO(content), "application/pdf")


class TestContractParserWiring:
    """Injection get_current_user et flux route → commande → réponse."""

    def test_extract_from_pdf_end_to_end_with_overrides(self, client: TestClient):
        """
        Flux complet : POST avec get_current_user overridé → commande mockée → 200.
        Vérifie que la chaîne router → commands.extract_contract_from_pdf est utilisée.
        """
        from app.core.security import get_current_user

        user = _make_user()
        app.dependency_overrides[get_current_user] = lambda: user

        fake_result = ExtractionResultDto(
            extracted_data={"first_name": "Jean", "hire_date": "2024-01-15"},
            confidence="high",
            warnings=[],
        )

        try:
            with patch(
                "app.modules.contract_parser.api.router.commands.extract_contract_from_pdf",
                return_value=fake_result,
            ) as mock_cmd:
                response = client.post(
                    "/api/contract-parser/extract-from-pdf",
                    files={"file": _pdf_file()},
                )
            assert response.status_code == 200
            mock_cmd.assert_called_once()
            # Les bytes du fichier uploadé ont bien été passés à la commande
            call_args = mock_cmd.call_args
            assert call_args[0][0] == b"%PDF-1.4 minimal"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_extract_rib_from_pdf_wiring(self, client: TestClient):
        """Flux extract-rib : auth override + commande appelée avec le contenu du fichier."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_user()
        try:
            with patch(
                "app.modules.contract_parser.api.router.commands.extract_rib_from_pdf",
                return_value=ExtractionResultDto(
                    extracted_data={"iban": "FR76", "bic": "X"},
                    confidence="medium",
                    warnings=[],
                ),
            ) as mock_cmd:
                response = client.post(
                    "/api/contract-parser/extract-rib-from-pdf",
                    files={"file": _pdf_file(b"rib content")},
                )
            assert response.status_code == 200
            mock_cmd.assert_called_once_with(b"rib content")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_extract_questionnaire_from_pdf_wiring(self, client: TestClient):
        """Flux extract-questionnaire : même principe, flux bout en bout."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_user()
        try:
            with patch(
                "app.modules.contract_parser.api.router.commands.extract_questionnaire_from_pdf",
                return_value=ExtractionResultDto(
                    extracted_data={"job_title": "Dev"},
                    confidence="low",
                    warnings=["Vérifier les dates"],
                ),
            ) as mock_cmd:
                response = client.post(
                    "/api/contract-parser/extract-questionnaire-from-pdf",
                    files={"file": _pdf_file(b"questionnaire content")},
                )
            assert response.status_code == 200
            data = response.json()
            assert data["extracted_data"]["job_title"] == "Dev"
            assert data["warnings"] == ["Vérifier les dates"]
            mock_cmd.assert_called_once_with(b"questionnaire content")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

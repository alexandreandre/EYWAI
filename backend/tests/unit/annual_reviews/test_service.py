"""
Tests unitaires du service applicatif annual_reviews (application/service.py).

Dépendances (repository, pdf_generator) mockées.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.annual_reviews.application import service


class TestGetRepository:
    """get_repository()."""

    def test_returns_repository_instance(self):
        """Retourne une instance conforme à IAnnualReviewRepository."""
        repo = service.get_repository()
        assert repo is not None
        assert hasattr(repo, "list_by_company")
        assert hasattr(repo, "get_by_id")
        assert hasattr(repo, "create")
        assert hasattr(repo, "update")
        assert hasattr(repo, "delete")
        assert hasattr(repo, "get_employee_company_id")
        assert hasattr(repo, "get_employee_by_id")
        assert hasattr(repo, "get_company_by_id")


class TestGetPdfGenerator:
    """get_pdf_generator()."""

    def test_returns_pdf_generator_instance(self):
        """Retourne un objet avec une méthode generate(review_data, employee_data, company_data)."""
        gen = service.get_pdf_generator()
        assert gen is not None
        assert hasattr(gen, "generate")
        assert callable(getattr(gen, "generate"))


class TestGenerateAnnualReviewPdf:
    """generate_annual_review_pdf avec repo et pdf_generator injectés (mockés)."""

    def test_raises_lookup_error_when_review_not_found(self):
        """Entretien non trouvé → LookupError."""
        repo = MagicMock()
        repo.get_by_id.return_value = None
        # get_annual_review_for_pdf retourne None si review non trouvé
        with patch.object(
            service.queries,
            "get_annual_review_for_pdf",
            return_value=None,
        ):
            with pytest.raises(LookupError) as exc_info:
                service.generate_annual_review_pdf(
                    "rev-unknown",
                    "co-1",
                    "user-1",
                    is_rh=True,
                    repository=repo,
                )
            assert "Entretien" in str(exc_info.value) or "trouvé" in str(exc_info.value).lower()

    def test_raises_lookup_error_when_employee_not_found(self):
        """Données entretien OK mais employé non trouvé → LookupError."""
        repo = MagicMock()
        repo.get_employee_by_id.return_value = None
        review_data = {
            "id": "rev-1",
            "company_id": "co-1",
            "employee_id": "emp-1",
            "year": 2024,
            "status": "cloture",
        }
        with patch.object(
            service.queries,
            "get_annual_review_for_pdf",
            return_value=review_data,
        ):
            with pytest.raises(LookupError) as exc_info:
                service.generate_annual_review_pdf(
                    "rev-1",
                    "co-1",
                    "user-1",
                    is_rh=True,
                    repository=repo,
                )
            assert "Employé" in str(exc_info.value) or "trouvé" in str(exc_info.value).lower()

    def test_returns_pdf_bytes_and_filename(self):
        """Données complètes → (pdf_bytes, filename)."""
        repo = MagicMock()
        review_data = {
            "id": "rev-1",
            "company_id": "co-1",
            "employee_id": "emp-1",
            "year": 2024,
            "status": "cloture",
        }
        employee_data = {
            "id": "emp-1",
            "first_name": "Jean",
            "last_name": "Dupont",
            "job_title": "Développeur",
        }
        company_data = {"id": "co-1", "name": "Ma Société"}
        repo.get_employee_by_id.return_value = employee_data
        repo.get_company_by_id.return_value = company_data

        pdf_gen = MagicMock()
        pdf_gen.generate.return_value = b"%PDF-1.4 fake content"

        with patch.object(
            service.queries,
            "get_annual_review_for_pdf",
            return_value=review_data,
        ):
            pdf_bytes, filename = service.generate_annual_review_pdf(
                "rev-1",
                "co-1",
                "user-1",
                is_rh=True,
                repository=repo,
                pdf_generator=pdf_gen,
            )

        assert pdf_bytes == b"%PDF-1.4 fake content"
        assert "entretien" in filename.lower()
        assert "Jean" in filename
        assert "Dupont" in filename
        assert "2024" in filename
        assert filename.endswith(".pdf")
        pdf_gen.generate.assert_called_once()
        call_args = pdf_gen.generate.call_args[0]
        assert call_args[0] == review_data
        assert call_args[1] == employee_data
        assert call_args[2] == company_data

    def test_filename_sanitizes_spaces_in_names(self):
        """Le filename remplace les espaces dans prénom/nom par des underscores."""
        repo = MagicMock()
        review_data = {
            "id": "rev-1",
            "company_id": "co-1",
            "employee_id": "emp-1",
            "year": 2024,
            "status": "cloture",
        }
        employee_data = {
            "id": "emp-1",
            "first_name": "Jean Pierre",
            "last_name": "Dupont Martin",
            "job_title": "Dev",
        }
        repo.get_employee_by_id.return_value = employee_data
        repo.get_company_by_id.return_value = {}

        pdf_gen = MagicMock()
        pdf_gen.generate.return_value = b"pdf"

        with patch.object(
            service.queries,
            "get_annual_review_for_pdf",
            return_value=review_data,
        ):
            _, filename = service.generate_annual_review_pdf(
                "rev-1",
                "co-1",
                "user-1",
                is_rh=True,
                repository=repo,
                pdf_generator=pdf_gen,
            )

        assert " " not in filename or "Jean_Pierre" in filename or "Dupont_Martin" in filename

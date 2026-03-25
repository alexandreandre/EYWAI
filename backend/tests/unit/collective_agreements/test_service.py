"""
Tests du service applicatif CollectiveAgreementsService.

Dépendances mockées : repository, storage, text_cache, pdf_extractor, chat_provider.
Vérification des droits (super_admin, has_rh_access), délégation au repository
et conversion des exceptions du domain en HTTPException.
"""
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.modules.collective_agreements.application.dto import (
    CatalogCreateInput,
    UploadUrlOutput,
    QuestionOutput,
)
from app.modules.collective_agreements.application.service import CollectiveAgreementsService


def _make_service(
    repo=None,
    storage=None,
    text_cache=None,
    pdf_extractor=None,
    chat_provider=None,
):
    return CollectiveAgreementsService(
        repository=repo or MagicMock(),
        storage=storage or MagicMock(),
        text_cache=text_cache or MagicMock(),
        pdf_extractor=pdf_extractor or MagicMock(),
        chat_provider=chat_provider or MagicMock(),
    )


# --- list_catalog ---


class TestServiceListCatalog:
    """Service.list_catalog."""

    def test_returns_agreements_with_signed_url(self):
        repo = MagicMock()
        repo.list_catalog.return_value = [
            {"id": "agr-1", "name": "CC", "rules_pdf_path": "/catalog/a.pdf"}
        ]
        storage = MagicMock()
        storage.create_signed_url.return_value = "https://signed.url/pdf"
        svc = _make_service(repo=repo, storage=storage)

        result = svc.list_catalog()

        assert len(result) == 1
        assert result[0]["rules_pdf_url"] == "https://signed.url/pdf"
        repo.list_catalog.assert_called_once_with(
            sector=None, search=None, active_only=True
        )

    def test_list_catalog_with_filters(self):
        repo = MagicMock()
        repo.list_catalog.return_value = []
        svc = _make_service(repo=repo)

        svc.list_catalog(sector="IT", search="Syntec", active_only=False)

        repo.list_catalog.assert_called_once_with(
            sector="IT", search="Syntec", active_only=False
        )


# --- get_catalog_item ---


class TestServiceGetCatalogItem:
    """Service.get_catalog_item."""

    def test_returns_none_when_not_found(self):
        repo = MagicMock()
        repo.get_catalog_item.return_value = None
        svc = _make_service(repo=repo)

        result = svc.get_catalog_item("agr-unknown")

        assert result is None

    def test_adds_signed_url_when_found(self):
        repo = MagicMock()
        repo.get_catalog_item.return_value = {
            "id": "agr-1",
            "name": "CC",
            "rules_pdf_path": "/path.pdf",
        }
        storage = MagicMock()
        storage.create_signed_url.return_value = "https://signed.url"
        svc = _make_service(repo=repo, storage=storage)

        result = svc.get_catalog_item("agr-1")

        assert result["rules_pdf_url"] == "https://signed.url"


# --- get_upload_url ---


class TestServiceGetUploadUrl:
    """Service.get_upload_url."""

    def test_returns_path_and_signed_url(self):
        storage = MagicMock()
        storage.create_signed_upload_url.return_value = {
            "path": "catalog/2025-01-01-abc.pdf",
            "signedUrl": "https://upload.url",
        }
        svc = _make_service(storage=storage)

        result = svc.get_upload_url("doc.pdf")

        assert isinstance(result, UploadUrlOutput)
        assert result.path == "catalog/2025-01-01-abc.pdf"
        assert result.signed_url == "https://upload.url"
        assert storage.create_signed_upload_url.called
        call_path = storage.create_signed_upload_url.call_args[0][0]
        assert call_path.startswith("catalog/")
        assert call_path.endswith(".pdf")


# --- create_catalog_item ---


class TestServiceCreateCatalogItem:
    """Service.create_catalog_item."""

    def test_raises_403_when_not_super_admin(self):
        data = CatalogCreateInput(
            name="CC",
            idcc="1486",
            description=None,
            sector=None,
            effective_date=None,
            is_active=True,
            rules_pdf_path=None,
            rules_pdf_filename=None,
        )
        svc = _make_service()

        with pytest.raises(HTTPException) as exc_info:
            svc.create_catalog_item(data, is_super_admin=False)

        assert exc_info.value.status_code == 403
        assert "super administrateur" in exc_info.value.detail

    def test_creates_via_repo_when_super_admin(self):
        repo = MagicMock()
        repo.create_catalog_item.return_value = {"id": "new-id", "name": "CC"}
        data = CatalogCreateInput(
            name="CC",
            idcc="1486",
            description=None,
            sector=None,
            effective_date=None,
            is_active=True,
            rules_pdf_path="/catalog/x.pdf",
            rules_pdf_filename="x.pdf",
        )
        svc = _make_service(repo=repo)

        result = svc.create_catalog_item(data, is_super_admin=True)

        assert result["id"] == "new-id"
        repo.create_catalog_item.assert_called_once()
        call_data = repo.create_catalog_item.call_args[0][0]
        assert call_data["name"] == "CC"
        assert call_data["idcc"] == "1486"


# --- update_catalog_item ---


class TestServiceUpdateCatalogItem:
    """Service.update_catalog_item."""

    def test_raises_403_when_not_super_admin(self):
        svc = _make_service()
        with pytest.raises(HTTPException) as exc_info:
            svc.update_catalog_item("agr-1", {"name": "X"}, is_super_admin=False)
        assert exc_info.value.status_code == 403

    def test_raises_400_when_no_data_to_update(self):
        svc = _make_service()
        with pytest.raises(HTTPException) as exc_info:
            svc.update_catalog_item("agr-1", {}, is_super_admin=True)
        assert exc_info.value.status_code == 400
        assert "Aucune donnée" in exc_info.value.detail

    def test_removes_old_pdf_when_rules_pdf_path_set_to_none(self):
        repo = MagicMock()
        repo.get_catalog_item_rules_path.return_value = "/old/path.pdf"
        repo.update_catalog_item.return_value = {"id": "agr-1", "rules_pdf_path": None}
        storage = MagicMock()
        svc = _make_service(repo=repo, storage=storage)

        svc.update_catalog_item(
            "agr-1",
            {"name": "X", "rules_pdf_path": None},
            is_super_admin=True,
        )

        storage.remove.assert_called_once_with(["/old/path.pdf"])
        repo.update_catalog_item.assert_called_once()


# --- delete_catalog_item ---


class TestServiceDeleteCatalogItem:
    """Service.delete_catalog_item."""

    def test_raises_403_when_not_super_admin(self):
        svc = _make_service()
        with pytest.raises(HTTPException) as exc_info:
            svc.delete_catalog_item("agr-1", is_super_admin=False)
        assert exc_info.value.status_code == 403

    def test_removes_pdf_and_deletes_in_repo(self):
        repo = MagicMock()
        repo.get_catalog_item_rules_path.return_value = "/catalog/doc.pdf"
        repo.delete_catalog_item.return_value = True
        storage = MagicMock()
        svc = _make_service(repo=repo, storage=storage)

        result = svc.delete_catalog_item("agr-1", is_super_admin=True)

        assert result is True
        storage.remove.assert_called_once_with(["/catalog/doc.pdf"])
        repo.delete_catalog_item.assert_called_once_with("agr-1")


# --- get_my_company_agreements ---


class TestServiceGetMyCompanyAgreements:
    """Service.get_my_company_agreements."""

    def test_raises_403_when_no_rh_access(self):
        svc = _make_service()
        with pytest.raises(HTTPException) as exc_info:
            svc.get_my_company_agreements("c1", has_rh_access=False)
        assert exc_info.value.status_code == 403
        assert "non autorisé" in exc_info.value.detail

    def test_returns_assignments_with_signed_url_on_details(self):
        repo = MagicMock()
        repo.get_my_company_assignments.return_value = [
            {
                "id": "a1",
                "agreement_details": {"name": "CC", "rules_pdf_path": "/p.pdf"},
            }
        ]
        storage = MagicMock()
        storage.create_signed_url.return_value = "https://signed.url"
        svc = _make_service(repo=repo, storage=storage)

        result = svc.get_my_company_agreements("c1", has_rh_access=True)

        assert len(result) == 1
        assert result[0]["agreement_details"]["rules_pdf_url"] == "https://signed.url"


# --- assign_to_company / unassign_from_company ---


class TestServiceAssignUnassign:
    """Service assign / unassign."""

    def test_assign_raises_403_without_rh_access(self):
        svc = _make_service()
        with pytest.raises(HTTPException) as exc_info:
            svc.assign_to_company("c1", "agr-1", "user-1", has_rh_access=False)
        assert exc_info.value.status_code == 403

    def test_assign_returns_repo_result(self):
        repo = MagicMock()
        repo.assign_to_company.return_value = {"id": "assign-1"}
        svc = _make_service(repo=repo)
        result = svc.assign_to_company("c1", "agr-1", "user-1", has_rh_access=True)
        assert result == {"id": "assign-1"}

    def test_unassign_raises_403_without_rh_access(self):
        svc = _make_service()
        with pytest.raises(HTTPException) as exc_info:
            svc.unassign_from_company("a1", "c1", has_rh_access=False)
        assert exc_info.value.status_code == 403

    def test_unassign_returns_repo_result(self):
        repo = MagicMock()
        repo.unassign_from_company.return_value = True
        svc = _make_service(repo=repo)
        result = svc.unassign_from_company("a1", "c1", has_rh_access=True)
        assert result is True


# --- get_all_assignments ---


class TestServiceGetAllAssignments:
    """Service.get_all_assignments."""

    def test_raises_403_when_not_super_admin(self):
        svc = _make_service()
        with pytest.raises(HTTPException) as exc_info:
            svc.get_all_assignments(is_super_admin=False)
        assert exc_info.value.status_code == 403

    def test_returns_repo_result_with_signed_urls(self):
        repo = MagicMock()
        repo.get_all_assignments_by_company.return_value = [
            {
                "id": "c1",
                "company_name": "Co",
                "assigned_agreements": [
                    {"agreement_details": {"rules_pdf_path": "/p.pdf"}}
                ],
            }
        ]
        storage = MagicMock()
        storage.create_signed_url.return_value = "https://signed.url"
        svc = _make_service(repo=repo, storage=storage)

        result = svc.get_all_assignments(is_super_admin=True)

        assert len(result) == 1
        assert result[0]["assigned_agreements"][0]["agreement_details"]["rules_pdf_url"] == "https://signed.url"


# --- ask_question ---


class TestServiceAskQuestion:
    """Service.ask_question."""

    def test_raises_403_without_rh_access(self):
        svc = _make_service()
        with pytest.raises(HTTPException) as exc_info:
            svc.ask_question("agr-1", "Q?", "c1", has_rh_access=False)
        assert exc_info.value.status_code == 403

    def test_raises_403_when_convention_not_assigned_to_company(self):
        repo = MagicMock()
        repo.check_assignment_exists.return_value = False
        svc = _make_service(repo=repo)
        with pytest.raises(HTTPException) as exc_info:
            svc.ask_question("agr-1", "Q?", "c1", has_rh_access=True)
        assert exc_info.value.status_code == 403
        assert "n'est pas assignée" in exc_info.value.detail

    def test_raises_404_when_agreement_not_found(self):
        repo = MagicMock()
        repo.check_assignment_exists.return_value = True
        repo.get_agreement_for_chat.return_value = None
        svc = _make_service(repo=repo)
        with pytest.raises(HTTPException) as exc_info:
            svc.ask_question("agr-1", "Q?", "c1", has_rh_access=True)
        assert exc_info.value.status_code == 404

    def test_raises_400_when_no_pdf_available(self):
        repo = MagicMock()
        repo.check_assignment_exists.return_value = True
        repo.get_agreement_for_chat.return_value = {
            "id": "agr-1",
            "name": "CC",
            "idcc": "1486",
            "description": "",
            "rules_pdf_path": None,
        }
        svc = _make_service(repo=repo)
        with pytest.raises(HTTPException) as exc_info:
            svc.ask_question("agr-1", "Q?", "c1", has_rh_access=True)
        assert exc_info.value.status_code in (400, 500)
        assert "PDF" in exc_info.value.detail

    def test_returns_answer_when_cache_and_chat_ok(self):
        repo = MagicMock()
        repo.check_assignment_exists.return_value = True
        repo.get_agreement_for_chat.return_value = {
            "id": "agr-1",
            "name": "CC Syntec",
            "idcc": "1486",
            "description": "",
            "rules_pdf_path": "/catalog/doc.pdf",
        }
        storage = MagicMock()
        storage.create_signed_url.return_value = "https://pdf.url"
        text_cache = MagicMock()
        text_cache.get_full_text.return_value = "Texte du PDF en cache..."
        chat = MagicMock()
        chat.answer.return_value = "Selon l'article 5, les congés sont de 25 jours."
        svc = _make_service(
            repo=repo,
            storage=storage,
            text_cache=text_cache,
            chat_provider=chat,
        )

        result = svc.ask_question(
            "agr-1", "Quelle est la durée des congés ?", "c1", has_rh_access=True
        )

        assert isinstance(result, QuestionOutput)
        assert result.agreement_name == "CC Syntec"
        assert "article 5" in result.answer or "25" in result.answer
        text_cache.get_full_text.assert_called_once_with("agr-1")
        chat.answer.assert_called_once()


# --- refresh_text_cache ---


class TestServiceRefreshTextCache:
    """Service.refresh_text_cache."""

    def test_raises_403_when_not_super_admin(self):
        svc = _make_service()
        with pytest.raises(HTTPException) as exc_info:
            svc.refresh_text_cache("agr-1", is_super_admin=False)
        assert exc_info.value.status_code == 403

    def test_deletes_cache_and_refetches_text(self):
        repo = MagicMock()
        repo.get_agreement_for_chat.return_value = {
            "id": "agr-1",
            "name": "CC",
            "rules_pdf_path": "/p.pdf",
        }
        storage = MagicMock()
        storage.create_signed_url.return_value = "https://pdf.url"
        text_cache = MagicMock()
        text_cache.get_full_text.return_value = None  # après delete, cache vide
        pdf_extractor = MagicMock()
        pdf_extractor.extract.return_value = "Extracted text"
        svc = _make_service(
            repo=repo,
            storage=storage,
            text_cache=text_cache,
            pdf_extractor=pdf_extractor,
        )

        svc.refresh_text_cache("agr-1", is_super_admin=True)

        text_cache.delete.assert_called_once_with("agr-1")
        text_cache.set_full_text.assert_called_once()
        call_args = text_cache.set_full_text.call_args[0]
        assert call_args[0] == "agr-1"
        assert call_args[1] == "Extracted text"
        assert call_args[2] == len("Extracted text")

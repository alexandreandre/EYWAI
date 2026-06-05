"""Tests génération PDF documents convention (texte intégral + synthèse) et accès."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.collective_agreements.application.documents import (
    CCDocumentService,
    DOC_FULL_TEXT,
    DOC_SYNTHESIS,
    _hash_text,
)
from app.modules.collective_agreements.domain.exceptions import (
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.modules.collective_agreements.infrastructure.document_pdf import (
    _render_kali_text_to_html,
    build_full_text_pdf,
    build_synthesis_pdf,
)


class TestDocumentPdfRendering:
    def test_kali_html_rendered_not_escaped(self):
        html = _render_kali_text_to_html(
            """## Texte salarial : Bretagne Accord test

Bretagne Accord test

Article 1er
<p align="left">Salaire minimal <strong>1 800 €</strong>.</p><center><table border="1"><tr><th>Niveau</th><td>150</td></tr></table></center>""",
            idcc="1597",
        )
        assert "<table" in html
        assert "&lt;table" not in html
        assert "Salaire minimal" in html
        assert "Bretagne Accord test" not in html or html.count("Bretagne Accord test") == 1

    def test_kali_metadata_and_ids_stripped(self):
        html = _render_kali_text_to_html(
            """# Convention collective test
IDCC 1597
Source : https://www.legifrance.gouv.fr/example

## Section

Article KALIARTI000054066631
Article 1er
Contenu utile.""",
            idcc="1597",
        )
        assert "Source :" not in html
        assert "KALIARTI" not in html
        assert "Contenu utile" in html

    def test_full_text_pdf_is_pdf_bytes(self):
        pdf = build_full_text_pdf(
            title="CC Test",
            idcc="1597",
            full_text="# Titre\n\n## Texte salarial : IDF\n\nArticle 1\nContenu de l'article.",
        )
        assert pdf[:4] == b"%PDF"

    def test_synthesis_pdf_is_pdf_bytes(self):
        pdf = build_synthesis_pdf(
            title="CC Test",
            idcc="1597",
            synthesis_md="## Présentation\n\n- point un\n- point deux\n\n**Important** : vérifier.",
        )
        assert pdf[:4] == b"%PDF"


def _agreement():
    return {
        "id": "agr-1",
        "name": "Convention test",
        "idcc": "1597",
        "rules_pdf_path": None,
    }


def _build_service(*, agreement=None, full_text="Texte de base.", meta=None):
    agreements = MagicMock()
    agreements.get_catalog_item.return_value = agreement if agreement is not None else _agreement()
    agreements._repo.check_assignment_exists.return_value = True

    text_cache = MagicMock()
    text_cache.get_full_text.return_value = full_text
    text_cache.get_text_with_meta.return_value = meta

    svc = CCDocumentService(agreements=agreements, text_cache=text_cache)
    return svc, agreements, text_cache


class TestAccessControl:
    def test_not_found(self):
        svc, agreements, _ = _build_service()
        agreements.get_catalog_item.return_value = None
        with pytest.raises(NotFoundError):
            svc.get_document(
                "agr-1", DOC_FULL_TEXT,
                company_id="c1", has_rh_access=True, is_platform_admin=False,
            )

    def test_forbidden_without_rh(self):
        svc, _, _ = _build_service()
        with pytest.raises(ForbiddenError):
            svc.get_document(
                "agr-1", DOC_FULL_TEXT,
                company_id="c1", has_rh_access=False, is_platform_admin=False,
            )

    def test_forbidden_without_assignment(self):
        svc, agreements, _ = _build_service()
        agreements._repo.check_assignment_exists.return_value = False
        with pytest.raises(ForbiddenError):
            svc.get_document(
                "agr-1", DOC_FULL_TEXT,
                company_id="c1", has_rh_access=True, is_platform_admin=False,
            )

    def test_platform_admin_bypasses_assignment(self):
        svc, agreements, _ = _build_service()
        pdf, filename = svc.get_document(
            "agr-1", DOC_FULL_TEXT,
            company_id=None, has_rh_access=False, is_platform_admin=True,
        )
        assert pdf[:4] == b"%PDF"
        assert filename == "convention-1597-texte-integral.pdf"
        agreements._repo.check_assignment_exists.assert_not_called()

    def test_missing_text_raises_validation(self):
        svc, _, text_cache = _build_service(full_text=None)
        with pytest.raises(ValidationError):
            svc.get_document(
                "agr-1", DOC_FULL_TEXT,
                company_id="c1", has_rh_access=True, is_platform_admin=True,
            )


class TestSynthesisCache:
    def test_uses_cache_when_hash_matches(self, monkeypatch):
        full_text = "Texte de base de la convention."
        meta = {
            "synthesis_md": "## Synthèse en cache",
            "synthesis_source_hash": _hash_text(full_text),
            "synthesis_model": "test",
        }
        svc, _, text_cache = _build_service(full_text=full_text, meta=meta)

        called = MagicMock()
        monkeypatch.setattr(
            "app.modules.collective_agreements.application.documents.chat_completions_create",
            called,
        )

        pdf, filename = svc.get_document(
            "agr-1", DOC_SYNTHESIS,
            company_id="c1", has_rh_access=True, is_platform_admin=False,
        )
        assert pdf[:4] == b"%PDF"
        assert filename == "convention-1597-synthese.pdf"
        called.assert_not_called()
        text_cache.set_synthesis.assert_not_called()

    def test_generates_and_caches_when_no_cache(self, monkeypatch):
        full_text = "Texte de base de la convention."
        svc, _, text_cache = _build_service(full_text=full_text, meta=None)

        fake_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="## Synthèse générée"))]
        )
        monkeypatch.setattr(
            "app.modules.collective_agreements.application.documents.chat_completions_create",
            MagicMock(return_value=fake_response),
        )

        pdf, _ = svc.get_document(
            "agr-1", DOC_SYNTHESIS,
            company_id="c1", has_rh_access=True, is_platform_admin=False,
        )
        assert pdf[:4] == b"%PDF"
        text_cache.set_synthesis.assert_called_once()
        kwargs = text_cache.set_synthesis.call_args.kwargs
        assert kwargs["source_hash"] == _hash_text(full_text)
        assert kwargs["synthesis_md"] == "## Synthèse générée"

    def test_regenerates_when_hash_stale(self, monkeypatch):
        full_text = "Nouveau texte."
        meta = {
            "synthesis_md": "## Vieille synthèse",
            "synthesis_source_hash": "ancien-hash",
            "synthesis_model": "test",
        }
        svc, _, text_cache = _build_service(full_text=full_text, meta=meta)

        fake_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="## Synthèse à jour"))]
        )
        gen = MagicMock(return_value=fake_response)
        monkeypatch.setattr(
            "app.modules.collective_agreements.application.documents.chat_completions_create",
            gen,
        )

        svc.get_document(
            "agr-1", DOC_SYNTHESIS,
            company_id="c1", has_rh_access=True, is_platform_admin=False,
        )
        gen.assert_called_once()
        text_cache.set_synthesis.assert_called_once()

    def test_unknown_doc_kind(self):
        svc, _, _ = _build_service()
        with pytest.raises(ValidationError):
            svc.get_document(
                "agr-1", "autre",
                company_id="c1", has_rh_access=True, is_platform_admin=True,
            )

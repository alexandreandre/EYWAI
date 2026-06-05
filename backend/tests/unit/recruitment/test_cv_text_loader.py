"""Tests unitaires du chargement de texte CV pour le scoring."""

from unittest.mock import MagicMock, patch

from app.modules.recruitment.application.cv_text_loader import load_cv_text


class TestLoadCvText:
    def test_no_cv_url(self):
        text, status = load_cv_text(None)
        assert text == ""
        assert status is None

    @patch("app.modules.recruitment.application.cv_text_loader.requests.get")
    @patch("app.modules.recruitment.application.cv_text_loader.extract_document_text")
    def test_extracts_pdf_text(self, mock_extract, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            content=b"%PDF",
            headers={"content-type": "application/pdf"},
            raise_for_status=MagicMock(),
        )
        mock_extract.return_value = (
            "Expérience Python développeur senior plus de cinq ans en entreprise",
            "PDF natif",
        )

        text, status = load_cv_text("https://example.com/cv.pdf?token=abc")

        assert "Python" in text
        assert status is not None
        assert "PDF natif" in status

    @patch("app.modules.recruitment.application.cv_text_loader.requests.get")
    def test_download_failure(self, mock_get):
        mock_get.side_effect = OSError("network")

        text, status = load_cv_text("https://example.com/cv.pdf")

        assert text == ""
        assert status is not None
        assert "téléchargement" in status.lower()

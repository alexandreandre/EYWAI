"""
Extraction de texte transverse depuis un document uploadé (PDF ou image).

Centralise la lecture de documents pour les fonctionnalités qui ont besoin
d'envoyer du texte brut à un LLM (ex. relevé de pointeuse sur la page
Calendriers RH). Supporte :
- PDF natif (pdfplumber, puis PyPDF2 en repli) ;
- PDF scanné (OCR Tesseract via pdf2image) ;
- image seule JPG/PNG/WEBP/TIFF (OCR Tesseract direct).

Les dépendances OCR (pdf2image, pytesseract, Pillow) sont optionnelles :
si elles sont absentes, seul le texte natif des PDF est exploité.
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

try:
    import pdfplumber

    _PDFPLUMBER_AVAILABLE = True
except ImportError:  # pragma: no cover - dépend de l'environnement
    _PDFPLUMBER_AVAILABLE = False

try:
    import PyPDF2

    _PYPDF2_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYPDF2_AVAILABLE = False

try:
    from pdf2image import convert_from_bytes
    import pytesseract
    from PIL import Image, ImageEnhance

    _OCR_AVAILABLE = True
except ImportError:  # pragma: no cover
    _OCR_AVAILABLE = False


_PDF_EXTENSIONS = (".pdf",)
_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp")
SUPPORTED_EXTENSIONS = _PDF_EXTENSIONS + _IMAGE_EXTENSIONS


class DocumentExtractionError(Exception):
    """Erreur métier lors de l'extraction de texte d'un document."""


def is_supported_document(filename: str | None) -> bool:
    if not filename:
        return False
    lowered = filename.lower()
    return lowered.endswith(SUPPORTED_EXTENSIONS)


def _is_image(filename: str | None) -> bool:
    return bool(filename) and filename.lower().endswith(_IMAGE_EXTENSIONS)


def _preprocess_image(image: "Image.Image") -> "Image.Image":
    image = image.convert("L")
    image = ImageEnhance.Contrast(image).enhance(2.0)
    image = ImageEnhance.Sharpness(image).enhance(1.5)
    return image


def _ocr_image(image: "Image.Image") -> str:
    processed = _preprocess_image(image)
    return pytesseract.image_to_string(processed, lang="fra", config=r"--oem 3 --psm 6")


def _extract_pdf_native(file_content: bytes) -> str:
    if _PDFPLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                text = "\n".join(
                    page.extract_text() or "" for page in pdf.pages
                ).strip()
            if len(text) > 60:
                return text
        except Exception as exc:  # pragma: no cover - dépend du fichier
            logger.warning("pdfplumber a échoué: %s", exc)

    if _PYPDF2_AVAILABLE:
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text = "\n".join(
                (page.extract_text() or "") for page in reader.pages
            ).strip()
            if len(text) > 60:
                return text
        except Exception as exc:  # pragma: no cover
            logger.warning("PyPDF2 a échoué: %s", exc)

    return ""


def _extract_pdf_ocr(file_content: bytes, max_pages: int = 8) -> str:
    if not _OCR_AVAILABLE:
        return ""
    try:
        images = convert_from_bytes(
            file_content, dpi=300, first_page=1, last_page=max_pages
        )
        return "\n".join(_ocr_image(img) for img in images).strip()
    except Exception as exc:  # pragma: no cover
        logger.warning("OCR PDF a échoué: %s", exc)
        return ""


def _extract_image(file_content: bytes) -> str:
    if not _OCR_AVAILABLE:
        raise DocumentExtractionError(
            "La lecture des images nécessite l'OCR (Tesseract), indisponible sur ce serveur."
        )
    try:
        image = Image.open(io.BytesIO(file_content))
        return _ocr_image(image).strip()
    except DocumentExtractionError:
        raise
    except Exception as exc:  # pragma: no cover
        raise DocumentExtractionError(
            "Impossible de lire l'image fournie."
        ) from exc


def extract_document_text(file_content: bytes, filename: str | None) -> tuple[str, str]:
    """
    Renvoie (texte, méthode) pour un PDF ou une image.

    Lève DocumentExtractionError si aucun texte exploitable n'a pu être extrait
    ou si le format n'est pas supporté.
    """
    if not file_content:
        raise DocumentExtractionError("Le fichier est vide.")
    if not is_supported_document(filename):
        raise DocumentExtractionError(
            "Format non supporté. Formats acceptés : PDF, JPG, PNG."
        )

    if _is_image(filename):
        text = _extract_image(file_content)
        if len(text) < 10:
            raise DocumentExtractionError(
                "Aucun texte n'a pu être lu dans l'image (qualité insuffisante ?)."
            )
        return text, "OCR image (Tesseract)"

    # PDF : texte natif puis OCR en repli
    text = _extract_pdf_native(file_content)
    if len(text) > 60:
        return text, "PDF natif"

    ocr_text = _extract_pdf_ocr(file_content)
    if len(ocr_text) > 30:
        return ocr_text, "OCR PDF (Tesseract)"

    if text and len(text) > 20:
        return text, "PDF natif (qualité limitée)"

    raise DocumentExtractionError(
        "Impossible d'extraire le texte du document avec les méthodes disponibles."
    )

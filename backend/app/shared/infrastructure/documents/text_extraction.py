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
import os
import re
from dataclasses import dataclass, field

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

_CEGID_PARTIAL_SIGNATURE = re.compile(
    r"pointages?\s+[\"']?retenu|Total\s+pour\s+la\s+semaine",
    re.IGNORECASE,
)
_BANQUE_HEURES_SIGNATURE = re.compile(r"BANQUE\s+HEURES", re.IGNORECASE)
_OCR_RELIABILITY_MIN_SCORE = 8
_OCR_PSM_MODES = (3, 4, 6)
_DEFAULT_OCR_MAX_PAGES = 120
_DEFAULT_OCR_DPI = 300
_DEFAULT_VISION_MAX_BYTES = 8 * 1024 * 1024
_DEFAULT_VISION_MAX_EDGE = 2400


@dataclass
class ExtractionMetadata:
    """Métadonnées d'extraction pour audit et alertes."""

    truncated: bool = False
    truncation_reason: str | None = None
    ocr_pages_total: int = 0
    ocr_pages_processed: int = 0
    ocr_psm_used: int | None = None
    cegid_signature_detected: bool = False
    post_processed: bool = False
    warnings: list[str] = field(default_factory=list)


class DocumentExtractionError(Exception):
    """Erreur métier lors de l'extraction de texte d'un document."""


def _ocr_max_pages() -> int:
    raw = os.getenv("TIMESHEET_OCR_MAX_PAGES", str(_DEFAULT_OCR_MAX_PAGES)).strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_OCR_MAX_PAGES


def _ocr_dpi() -> int:
    raw = os.getenv("TIMESHEET_OCR_DPI", str(_DEFAULT_OCR_DPI)).strip()
    try:
        return max(72, int(raw))
    except ValueError:
        return _DEFAULT_OCR_DPI


def _vision_max_bytes() -> int:
    raw = os.getenv("TIMESHEET_VISION_MAX_BYTES", str(_DEFAULT_VISION_MAX_BYTES)).strip()
    try:
        return max(512_000, int(raw))
    except ValueError:
        return _DEFAULT_VISION_MAX_BYTES


def _vision_max_edge() -> int:
    raw = os.getenv("TIMESHEET_VISION_MAX_EDGE", str(_DEFAULT_VISION_MAX_EDGE)).strip()
    try:
        return max(800, int(raw))
    except ValueError:
        return _DEFAULT_VISION_MAX_EDGE


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


def _ocr_image_with_psm(image: "Image.Image", psm: int) -> str:
    processed = _preprocess_image(image)
    config = f"--oem 3 --psm {psm}"
    return pytesseract.image_to_string(processed, lang="fra", config=config)


def score_timesheet_ocr_text(text: str) -> int:
    """Score heuristique : plus c'est haut, plus le texte ressemble à un relevé pointage."""
    if not text:
        return 0
    score = 0
    if _CEGID_PARTIAL_SIGNATURE.search(text):
        score += 3
    if _BANQUE_HEURES_SIGNATURE.search(text):
        score += 5
    score += len(re.findall(r"#\s*\d{1,2}[:.;]\d{2}", text))
    score += len(re.findall(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", text))
    score += len(re.findall(r"Total\s+pour\s+la\s+semaine", text, re.IGNORECASE)) * 5
    score += len(re.findall(r"^\d{4,6}\s+[A-Za-zÀ-ÿ]", text, re.MULTILINE)) * 2
    return score


def is_ocr_text_reliable(text: str) -> bool:
    """True si l'OCR est assez riche et structuré pour se passer de la vision."""
    cleaned = (text or "").strip()
    if len(cleaned) < 80:
        return False
    has_structure = bool(
        _CEGID_PARTIAL_SIGNATURE.search(cleaned)
        or _BANQUE_HEURES_SIGNATURE.search(cleaned)
    )
    if not has_structure:
        return False
    return _ocr_quality_score(cleaned) >= _OCR_RELIABILITY_MIN_SCORE


def _score_cegid_text(text: str) -> int:
    return score_timesheet_ocr_text(text)


def _ocr_quality_score(text: str) -> int:
    """Score orienté qualité parseur (pas seulement densité de dates OCR bruitées)."""
    score = score_timesheet_ocr_text(text)
    if _CEGID_PARTIAL_SIGNATURE.search(text or ""):
        score += 15
    if _BANQUE_HEURES_SIGNATURE.search(text or ""):
        score += 15
    if re.search(r"^\d{4,6}\s+[A-Za-zÀ-ÿ]", text or "", re.MULTILINE):
        score += 5
    return score


def _osd_rotate_image(image: "Image.Image") -> "Image.Image":
    if not _OCR_AVAILABLE:
        return image
    try:
        osd = pytesseract.image_to_osd(_preprocess_image(image))
        conf_match = re.search(r"Orientation confidence:\s+([\d.]+)", osd)
        rotate_match = re.search(r"Rotate:\s+(\d+)", osd)
        if conf_match and rotate_match:
            confidence = float(conf_match.group(1))
            angle = int(rotate_match.group(1)) % 360
            if confidence >= 5.0 and angle:
                return image.rotate(360 - angle, expand=True)
    except Exception as exc:  # pragma: no cover
        logger.debug("OSD Tesseract ignoré: %s", exc)
    return image


def _orientation_quality_score(text: str) -> int:
    """Score pour choisir la rotation (inclut feuilles manuscrites DEBUT/FIN)."""
    score = _ocr_quality_score(text)
    upper = (text or "").upper()
    for day in (
        "LUNDI",
        "MARDI",
        "MERCREDI",
        "JEUDI",
        "VENDREDI",
        "SAMEDI",
        "DIMANCHE",
    ):
        score += upper.count(day) * 5
    for label in ("DEBUT", "FIN"):
        score += upper.count(label) * 4
    if re.search(r"\bS\d{1,2}\b", upper):
        score += 8
    return score


def _orientation_variants(image: "Image.Image") -> list[tuple["Image.Image", int]]:
    """Variantes d'orientation à tester (image, angle appliqué depuis l'original)."""
    variants: list[tuple[Image.Image, int]] = [(image, 0)]
    oriented = _osd_rotate_image(image)
    if oriented is not image:
        variants.append((oriented, 0))
    for angle in (90, 180, 270):
        variants.append((image.rotate(angle, expand=True), angle))
    return variants


def _ocr_image_for_orientation(image: "Image.Image") -> tuple[str, int, int]:
    best_text = ""
    best_score = -1
    best_psm = 6
    for psm in _OCR_PSM_MODES:
        try:
            text = _ocr_image_with_psm(image, psm)
        except Exception:  # pragma: no cover
            continue
        score = _ocr_quality_score(text)
        if score > best_score or (score == best_score and len(text) > len(best_text)):
            best_text = text
            best_score = score
            best_psm = psm
    if not best_text:
        best_text = _ocr_image_with_psm(image, 6)
        best_score = _ocr_quality_score(best_text)
    return best_text, best_psm, best_score


def _ocr_image_adaptive(image: "Image.Image") -> tuple[str, int, "Image.Image", int]:
    """
    OCR avec auto-rotation. Retourne (texte, psm, image orientée, angle°).
    """
    if not _OCR_AVAILABLE:
        return "", 6, image, 0

    baseline_text, baseline_psm, _ = _ocr_image_for_orientation(image)
    if _orientation_quality_score(baseline_text) >= _OCR_RELIABILITY_MIN_SCORE:
        return baseline_text, baseline_psm, image, 0

    best_text, best_psm = baseline_text, baseline_psm
    best_score = _orientation_quality_score(baseline_text)
    best_image = image
    best_angle = 0

    for candidate, angle in _orientation_variants(image):
        if candidate is image and angle == 0:
            continue
        text, psm, _ = _ocr_image_for_orientation(candidate)
        score = _orientation_quality_score(text)
        if score > best_score or (score == best_score and len(text) > len(best_text)):
            best_text, best_psm, best_score = text, psm, score
            best_image = candidate
            best_angle = angle

    return best_text, best_psm, best_image, best_angle


def _post_process_ocr_text(text: str) -> str:
    """Normalisations légères pour relevés Cegid OCR."""
    if not text:
        return text
    lines = text.splitlines()
    merged: list[str] = []
    for line in lines:
        stripped = line.strip()
        if (
            merged
            and stripped
            and len(stripped) < 12
            and re.match(r"^\d{1,2}[:.;]\d{2}$", stripped)
            and not re.search(r"[#§]", merged[-1])
        ):
            merged[-1] = merged[-1] + " # " + stripped
        else:
            merged.append(line)
    text = "\n".join(merged)
    text = re.sub(r"([#§nN])\s*(\d{1,2})[;.](\d{2})", r"# \2:\3", text)
    text = re.sub(
        r"(Total\s+pour\s+la\s+semaine)\s*\n\s*(\d{1,2}/\d{4})",
        r"\1 \2",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _pdf_page_count(file_content: bytes) -> int:
    if _PYPDF2_AVAILABLE:
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            return len(reader.pages)
        except Exception as exc:  # pragma: no cover
            logger.warning("PyPDF2 page count a échoué: %s", exc)

    if _PDFPLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                return len(pdf.pages)
        except Exception as exc:  # pragma: no cover
            logger.warning("pdfplumber page count a échoué: %s", exc)

    return 0


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


def _extract_pdf_ocr(
    file_content: bytes,
    *,
    total_pages: int = 0,
    max_pages: int | None = None,
) -> tuple[str, int, int, int]:
    """OCR page par page. Retourne (texte, psm, pages_traitées, pages_totales)."""
    if not _OCR_AVAILABLE:
        return "", 6, 0, total_pages

    cap = max_pages if max_pages is not None else _ocr_max_pages()
    dpi = _ocr_dpi()
    pages_total = total_pages if total_pages > 0 else cap
    pages_to_process = min(pages_total, cap)

    parts: list[str] = []
    psm_used = 6
    calibrated_psm: int | None = None
    page_rotation: int = 0

    try:
        for page_num in range(1, pages_to_process + 1):
            logger.info("OCR page %s/%s (dpi=%s)", page_num, pages_total, dpi)
            images = convert_from_bytes(
                file_content,
                dpi=dpi,
                first_page=page_num,
                last_page=page_num,
            )
            if not images:
                break
            img = images[0]
            if page_num == 1:
                part, psm_used, _, page_rotation = _ocr_image_adaptive(img)
                calibrated_psm = psm_used
            else:
                assert calibrated_psm is not None
                oriented = (
                    img.rotate(page_rotation, expand=True)
                    if page_rotation
                    else img
                )
                part = _ocr_image_with_psm(oriented, calibrated_psm)
                psm_used = calibrated_psm
            parts.append(part)
    except Exception as exc:  # pragma: no cover
        logger.warning("OCR PDF a échoué: %s", exc)
        if not parts:
            return "", 6, 0, pages_total

    processed = len(parts)
    if total_pages <= 0:
        pages_total = processed
    return "\n".join(parts).strip(), psm_used, processed, pages_total


def _extract_image(file_content: bytes) -> tuple[str, int]:
    if not _OCR_AVAILABLE:
        raise DocumentExtractionError(
            "La lecture des images nécessite l'OCR (Tesseract), indisponible sur ce serveur."
        )
    try:
        image = Image.open(io.BytesIO(file_content))
        text, psm, _, _ = _ocr_image_adaptive(image)
        return text.strip(), psm
    except DocumentExtractionError:
        raise
    except Exception as exc:  # pragma: no cover
        raise DocumentExtractionError(
            "Impossible de lire l'image fournie."
        ) from exc


def _should_force_ocr(native_text: str) -> bool:
    """Force OCR si signature Cegid partielle mais peu de contenu exploitable.

    Certaines variantes Cegid (« Pointages retenu ») n'utilisent jamais de
    marqueur `#HH:MM` : le total journalier est juste en fin de ligne, et les
    lignes « Total pour la semaine » répétées suffisent à prouver que le texte
    natif est riche. N'exiger des marqueurs `#` que quand ce signal-là est
    absent évite de jeter un texte natif propre au profit d'un OCR plus bruité.
    """
    if not _CEGID_PARTIAL_SIGNATURE.search(native_text or ""):
        return False
    if _score_cegid_text(native_text) < 8:
        return True
    has_hash_markers = len(re.findall(r"#\s*\d", native_text or "")) >= 3
    has_weekly_totals = (
        len(re.findall(r"Total\s+pour\s+la\s+semaine", native_text or "", re.IGNORECASE))
        >= 2
    )
    if not has_hash_markers and not has_weekly_totals:
        return True
    return False


@dataclass
class RenderedPage:
    """Page rendue pour extraction hybride (vision + OCR)."""

    page_index: int
    png_bytes: bytes
    ocr_text: str
    ocr_psm: int | None = None
    vision_mime_type: str = "image/jpeg"


@dataclass
class RenderedDocument:
    pages: list[RenderedPage]
    warnings: list[str] = field(default_factory=list)
    pages_total: int = 0
    pages_processed: int = 0
    truncated: bool = False


def _image_to_png_bytes(image: "Image.Image") -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _encode_vision_jpeg(image: "Image.Image", *, quality: int) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def _image_to_vision_bytes(image: "Image.Image") -> tuple[bytes, str]:
    """
    Image optimisée pour l'API vision (JPEG, redimensionnée si nécessaire).
    OpenRouter refuse les payloads > ~30 Mo (scans phone en PNG 300 dpi).
    """
    if not _OCR_AVAILABLE:
        return _image_to_png_bytes(image.convert("RGB")), "image/png"

    rgb = image.convert("RGB")
    max_edge = _vision_max_edge()
    width, height = rgb.size
    if max(width, height) > max_edge:
        scale = max_edge / max(width, height)
        rgb = rgb.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.LANCZOS,
        )

    cap = _vision_max_bytes()
    quality = 88
    while True:
        best = _encode_vision_jpeg(rgb, quality=quality)
        if len(best) <= cap:
            return best, "image/jpeg"

        if quality > 45:
            quality -= 8
            continue

        width, height = rgb.size
        if max(width, height) <= 400:
            logger.warning(
                "Image vision encore volumineuse (%s octets) après compression.",
                len(best),
            )
            return best, "image/jpeg"

        rgb = rgb.resize(
            (max(1, width * 3 // 4), max(1, height * 3 // 4)),
            Image.LANCZOS,
        )
        quality = 80


def ensure_vision_image_under_limit(
    image_bytes: bytes,
    mime_type: str = "image/png",
) -> tuple[bytes, str]:
    """Repli : compresse un payload image déjà encodé avant envoi LLM."""
    if len(image_bytes) <= _vision_max_bytes():
        return image_bytes, mime_type
    if not _OCR_AVAILABLE:
        return image_bytes, mime_type
    try:
        image = Image.open(io.BytesIO(image_bytes))
        return _image_to_vision_bytes(image)
    except Exception as exc:  # pragma: no cover
        logger.warning("Compression vision de repli échouée: %s", exc)
        return image_bytes, mime_type


def render_document_pages(
    file_content: bytes, filename: str | None
) -> RenderedDocument:
    """
    Rend chaque page en PNG + OCR texte pour extraction IA hybride par page.
    """
    if not file_content:
        raise DocumentExtractionError("Le fichier est vide.")
    if not is_supported_document(filename):
        raise DocumentExtractionError(
            "Format non supporté. Formats acceptés : PDF, JPG, PNG."
        )

    warnings: list[str] = []
    cap = _ocr_max_pages()
    dpi = _ocr_dpi()

    if _is_image(filename):
        if not _OCR_AVAILABLE:
            raise DocumentExtractionError(
                "La lecture des images nécessite l'OCR (Tesseract), indisponible sur ce serveur."
            )
        image = Image.open(io.BytesIO(file_content))
        text, psm, oriented, _ = _ocr_image_adaptive(image)
        text = _post_process_ocr_text(text)
        vision_bytes, vision_mime = _image_to_vision_bytes(oriented)
        return RenderedDocument(
            pages=[
                RenderedPage(
                    page_index=1,
                    png_bytes=vision_bytes,
                    ocr_text=text,
                    ocr_psm=psm,
                    vision_mime_type=vision_mime,
                )
            ],
            pages_total=1,
            pages_processed=1,
        )

    pdf_pages = _pdf_page_count(file_content)
    pages_total = pdf_pages if pdf_pages > 0 else cap
    pages_to_process = min(pages_total, cap)
    rendered: list[RenderedPage] = []
    calibrated_psm: int | None = None
    page_rotation = 0

    if not _OCR_AVAILABLE:
        raise DocumentExtractionError(
            "L'extraction hybride nécessite l'OCR (Tesseract), indisponible sur ce serveur."
        )

    try:
        for page_num in range(1, pages_to_process + 1):
            images = convert_from_bytes(
                file_content,
                dpi=dpi,
                first_page=page_num,
                last_page=page_num,
            )
            if not images:
                break
            img = images[0]
            if page_num == 1:
                text, psm, oriented, page_rotation = _ocr_image_adaptive(img)
                calibrated_psm = psm
            else:
                assert calibrated_psm is not None
                oriented = (
                    img.rotate(page_rotation, expand=True) if page_rotation else img
                )
                text = _ocr_image_with_psm(oriented, calibrated_psm)
                psm = calibrated_psm
            text = _post_process_ocr_text(text)
            vision_bytes, vision_mime = _image_to_vision_bytes(oriented)
            rendered.append(
                RenderedPage(
                    page_index=page_num,
                    png_bytes=vision_bytes,
                    ocr_text=text,
                    ocr_psm=psm,
                    vision_mime_type=vision_mime,
                )
            )
    except Exception as exc:
        if not rendered:
            raise DocumentExtractionError(
                "Impossible de rendre les pages du document."
            ) from exc
        warnings.append(f"Rendu partiel : {exc}")

    truncated = pages_to_process < pages_total

    return RenderedDocument(
        pages=rendered,
        warnings=warnings,
        pages_total=pages_total,
        pages_processed=len(rendered),
        truncated=truncated,
    )


def extract_document_text(
    file_content: bytes, filename: str | None
) -> tuple[str, str, ExtractionMetadata]:
    """
    Renvoie (texte, méthode, métadonnées) pour un PDF ou une image.

    Lève DocumentExtractionError si aucun texte exploitable n'a pu être extrait
    ou si le format n'est pas supporté.
    """
    meta = ExtractionMetadata()
    if not file_content:
        raise DocumentExtractionError("Le fichier est vide.")
    if not is_supported_document(filename):
        raise DocumentExtractionError(
            "Format non supporté. Formats acceptés : PDF, JPG, PNG."
        )

    if _is_image(filename):
        text, psm = _extract_image(file_content)
        meta.ocr_psm_used = psm
        meta.ocr_pages_processed = 1
        meta.ocr_pages_total = 1
        meta.post_processed = True
        text = _post_process_ocr_text(text)
        meta.cegid_signature_detected = bool(_CEGID_PARTIAL_SIGNATURE.search(text))
        if len(text) < 10:
            raise DocumentExtractionError(
                "Aucun texte n'a pu être lu dans l'image (qualité insuffisante ?)."
            )
        return text, "OCR image (Tesseract)", meta

    pdf_pages = _pdf_page_count(file_content)
    native_text = _extract_pdf_native(file_content)
    meta.cegid_signature_detected = bool(_CEGID_PARTIAL_SIGNATURE.search(native_text))

    force_ocr = _should_force_ocr(native_text)
    if len(native_text) > 60 and not force_ocr:
        if pdf_pages > 0:
            meta.ocr_pages_total = pdf_pages
            meta.ocr_pages_processed = pdf_pages
        return native_text, "PDF natif", meta

    ocr_text, psm, processed, ocr_total = _extract_pdf_ocr(
        file_content, total_pages=pdf_pages
    )
    meta.ocr_pages_processed = processed
    meta.ocr_pages_total = ocr_total
    meta.ocr_psm_used = psm
    meta.post_processed = True
    ocr_text = _post_process_ocr_text(ocr_text)
    if _CEGID_PARTIAL_SIGNATURE.search(ocr_text):
        meta.cegid_signature_detected = True

    if len(ocr_text) > 30:
        if processed < ocr_total:
            meta.truncated = True
            meta.truncation_reason = (
                f"PDF de {ocr_total} pages, seules {processed} pages OCRisées."
            )
        if force_ocr and native_text:
            meta.warnings.append(
                "Texte natif partiel — OCR utilisé pour améliorer la lecture Cegid."
            )
        return ocr_text, "OCR PDF (Tesseract)", meta

    if native_text and len(native_text) > 20:
        if pdf_pages > 0:
            meta.ocr_pages_total = pdf_pages
            meta.ocr_pages_processed = pdf_pages
        if force_ocr:
            meta.warnings.append(
                "OCR insuffisant — texte natif partiel utilisé en repli."
            )
        return native_text, "PDF natif (qualité limitée)", meta

    raise DocumentExtractionError(
        "Impossible d'extraire le texte du document avec les méthodes disponibles."
    )


def extract_pdf_text_layer(file_content: bytes) -> str:
    """Texte de la couche PDF seul (pdfplumber), sans jamais déclencher l'OCR.

    Chaîne vide pour un scan, une image ou un PDF illisible : l'appelant du
    mode natif saute alors la détection de période plutôt que payer un OCR.
    """
    if not file_content or not file_content[:4] == b"%PDF":
        return ""
    try:
        return _extract_pdf_native(file_content) or ""
    except Exception:  # pragma: no cover - repli défensif
        return ""


__all__ = [
    "DocumentExtractionError",
    "ExtractionMetadata",
    "RenderedDocument",
    "RenderedPage",
    "SUPPORTED_EXTENSIONS",
    "ensure_vision_image_under_limit",
    "extract_document_text",
    "extract_pdf_text_layer",
    "is_ocr_text_reliable",
    "is_supported_document",
    "render_document_pages",
    "score_timesheet_ocr_text",
]

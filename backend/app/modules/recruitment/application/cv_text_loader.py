"""Chargement et extraction de texte depuis le CV d'un candidat (URL signée)."""

from __future__ import annotations

import logging
from urllib.parse import unquote, urlparse

import requests

from app.shared.infrastructure.documents.text_extraction import (
    DocumentExtractionError,
    extract_document_text,
    is_supported_document,
)

logger = logging.getLogger(__name__)

MAX_CV_CHARS = 12_000
_FETCH_TIMEOUT_S = 30


def _guess_filename(cv_url: str, content_type: str | None) -> str:
    path = unquote(urlparse(cv_url).path)
    basename = (path.rsplit("/", 1)[-1] if path else "") or "cv.pdf"
    if is_supported_document(basename):
        return basename
    ct = (content_type or "").lower()
    if "pdf" in ct:
        return "cv.pdf"
    if "jpeg" in ct or "jpg" in ct:
        return "cv.jpg"
    if "png" in ct:
        return "cv.png"
    if "webp" in ct:
        return "cv.webp"
    return basename


def load_cv_text(cv_url: str | None) -> tuple[str, str | None]:
    """
    Télécharge le CV et en extrait le texte.

    Retourne (texte, statut) où statut décrit le résultat pour le prompt IA
    (None si pas de CV).
    """
    if not (cv_url or "").strip():
        return "", None

    try:
        resp = requests.get(cv_url, timeout=_FETCH_TIMEOUT_S)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Téléchargement CV impossible: %s", exc)
        return "", "CV joint mais téléchargement impossible"

    content = resp.content
    if not content:
        return "", "CV joint mais fichier vide"

    filename = _guess_filename(cv_url, resp.headers.get("content-type"))
    if not is_supported_document(filename):
        return "", "CV joint mais format non analysable (PDF ou image attendu)"

    try:
        text, method = extract_document_text(content, filename)
    except DocumentExtractionError as exc:
        logger.warning("Extraction CV impossible: %s", exc)
        return "", f"CV joint mais texte non extractible ({exc})"

    text = text.strip()
    if len(text) < 30:
        return "", "CV joint mais contenu textuel trop court pour analyse fiable"

    truncated = False
    if len(text) > MAX_CV_CHARS:
        text = text[:MAX_CV_CHARS]
        truncated = True

    status = f"CV extrait ({method})"
    if truncated:
        status += f", tronqué à {MAX_CV_CHARS} caractères"
    return text, status

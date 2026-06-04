"""Utilitaires transverses de lecture de documents (PDF / image)."""

from app.shared.infrastructure.documents.text_extraction import (
    DocumentExtractionError,
    extract_document_text,
    is_supported_document,
)

__all__ = [
    "DocumentExtractionError",
    "extract_document_text",
    "is_supported_document",
]

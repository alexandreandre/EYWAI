"""Découpage d'un PDF en lots de pages pour envoi natif au modèle."""

from __future__ import annotations

import io
from dataclasses import dataclass

from PyPDF2 import PdfReader, PdfWriter

from app.shared.infrastructure.documents.text_extraction import DocumentExtractionError


@dataclass
class PdfBatch:
    content: bytes
    page_start: int  # 1-based, inclus
    page_end: int  # 1-based, inclus


def split_pdf_into_batches(
    file_content: bytes, *, batch_size: int, max_pages: int = 120
) -> list[PdfBatch]:
    try:
        reader = PdfReader(io.BytesIO(file_content))
        total = len(reader.pages)
    except Exception as exc:
        raise DocumentExtractionError("Impossible de lire le PDF.") from exc
    if total == 0:
        raise DocumentExtractionError("Le PDF ne contient aucune page.")

    total = min(total, max_pages)
    batch_size = max(1, batch_size)
    batches: list[PdfBatch] = []
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        writer = PdfWriter()
        for idx in range(start, end):
            writer.add_page(reader.pages[idx])
        buf = io.BytesIO()
        writer.write(buf)
        batches.append(
            PdfBatch(content=buf.getvalue(), page_start=start + 1, page_end=end)
        )
    return batches


__all__ = ["PdfBatch", "split_pdf_into_batches"]

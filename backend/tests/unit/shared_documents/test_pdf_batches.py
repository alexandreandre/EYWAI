"""Découpage PDF en lots : bornes 1-based, plafond de pages, PDF illisible."""

import io

import pytest
from PyPDF2 import PdfReader, PdfWriter

pytestmark = pytest.mark.unit


def _blank_pdf(pages: int) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_split_five_pages_in_batches_of_two():
    from app.shared.infrastructure.documents.pdf_batches import split_pdf_into_batches

    batches = split_pdf_into_batches(_blank_pdf(5), batch_size=2)

    assert [(b.page_start, b.page_end) for b in batches] == [(1, 2), (3, 4), (5, 5)]
    assert len(PdfReader(io.BytesIO(batches[0].content)).pages) == 2
    assert len(PdfReader(io.BytesIO(batches[2].content)).pages) == 1


def test_max_pages_caps_output():
    from app.shared.infrastructure.documents.pdf_batches import split_pdf_into_batches

    batches = split_pdf_into_batches(_blank_pdf(6), batch_size=4, max_pages=5)
    assert batches[-1].page_end == 5


def test_unreadable_pdf_raises():
    from app.shared.infrastructure.documents.pdf_batches import split_pdf_into_batches
    from app.shared.infrastructure.documents.text_extraction import DocumentExtractionError

    with pytest.raises(DocumentExtractionError):
        split_pdf_into_batches(b"pas un pdf", batch_size=2)

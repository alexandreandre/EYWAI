"""Tests score fiabilité OCR pour import pointages."""

from app.shared.infrastructure.documents.text_extraction import (
    is_ocr_text_reliable,
    score_timesheet_ocr_text,
)


def test_garbage_ocr_is_not_reliable():
    garbage = "RS PS PS CUITE\n" * 20
    assert score_timesheet_ocr_text(garbage) < 8
    assert not is_ocr_text_reliable(garbage)


def test_cegid_ocr_is_reliable():
    text = """
Pointages "retenu"
Du 25/05/2026 au 31/05/2026
196 ADAM YOUSSEF
Lundi 25/05/26 # 7:30
Total pour la semaine 22/2026: 37:29
""" * 3
    assert score_timesheet_ocr_text(text) >= 8
    assert is_ocr_text_reliable(text)


def test_banque_heures_ocr_is_reliable():
    text = """
BANQUE HEURES V1 25/05/2026
000009 DE ABREU Jose Solde HS avant période
27/04/2026 07:00 10:00 10:10 12:00 __:__ __:__ __:__ __:__ 8,83
""" * 5
    assert is_ocr_text_reliable(text)

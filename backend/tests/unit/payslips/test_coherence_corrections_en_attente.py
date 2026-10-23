"""Une correction en attente bloque la validation (règle 7)."""

from __future__ import annotations

import pytest

from app.modules.payslips.domain.coherence import MESSAGE_CORRECTION_EN_ATTENTE, raisons_de_ne_pas_valider

pytestmark = pytest.mark.unit


def test_une_correction_en_attente_empeche_de_valider():
    data = {"corrections_en_attente": [{"saisie_id": "c3", "ligne": "brut:precarite"}]}
    assert raisons_de_ne_pas_valider(data) == [MESSAGE_CORRECTION_EN_ATTENTE]


def test_sans_correction_en_attente_rien_ne_change():
    assert raisons_de_ne_pas_valider({}) == []
    assert raisons_de_ne_pas_valider({"corrections_en_attente": []}) == []

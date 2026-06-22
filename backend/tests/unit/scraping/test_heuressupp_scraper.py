"""Tests unitaires heures supplémentaires."""

import math

from scraping.heuressupp.heuressupp import legal_context_text, make_payload
from scraping.heuressupp.heuressupp_AI import _core_equal, extract_core
from scraping.heuressupp.spec import payload_to_core


def test_legal_context_mentions_majorations():
    text = legal_context_text()
    assert "25" in text and "50" in text
    assert "11,31" in text or "11.31" in text


def test_primary_core_stable():
    core = payload_to_core(make_payload())
    assert math.isclose(core["majoration_hs_25"], 0.25)
    assert math.isclose(core["deduction_effectif_1_19"], 1.5)


def test_extract_core_mocked_sonar(monkeypatch):
    reference = payload_to_core(make_payload())

    monkeypatch.setattr(
        "scraping.heuressupp.heuressupp_AI.extract_structured_json",
        lambda **kw: dict(reference),
    )
    core = extract_core()
    assert core is not None
    assert _core_equal(core, reference)

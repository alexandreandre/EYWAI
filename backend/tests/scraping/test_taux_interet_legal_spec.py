import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[2] / "scraping" / "taux_interet_legal"
SCRAPING = Path(__file__).resolve().parents[2] / "scraping"
for p in (str(SCRAPING), str(FOLDER)):
    if p not in sys.path:
        sys.path.insert(0, p)

from spec import SPEC  # noqa: E402  (spec.py du dossier taux_interet_legal)


def test_spec_identity():
    assert SPEC.config_key == "taux_interet_legal"
    assert SPEC.source_key == "TAUX_INTERET_LEGAL"
    assert SPEC.tier == "critical"


def test_signature_and_validation():
    sig = SPEC.extract_signature({"valeurs": {"taux_annuel": 0.0526}})
    assert sig == {"taux_annuel": 0.0526}
    assert SPEC.validate_signature({"taux_annuel": 0.0526}).ok
    assert not SPEC.validate_signature({"taux_annuel": 0.5}).ok  # 50 % = aberrant


def test_build_creates_flat_config():
    out = SPEC.build_config_data({"taux_annuel": 0.0526}, None)
    assert out == {"taux_annuel": 0.0526}

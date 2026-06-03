"""Helpers partagés pour les tests scraping."""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
SCRAPING_ROOT = BACKEND_ROOT / "scraping"
FIXTURES_ROOT = BACKEND_ROOT / "tests" / "fixtures" / "scraping"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(SCRAPING_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRAPING_ROOT))


def load_scraping_fixture(*parts: str) -> str:
    return FIXTURES_ROOT.joinpath(*parts).read_text(encoding="utf-8")

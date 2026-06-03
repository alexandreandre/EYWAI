import sys
from pathlib import Path

import pytest

from .helpers import FIXTURES_ROOT, SCRAPING_ROOT, load_scraping_fixture

BACKEND_ROOT = Path(__file__).resolve().parents[3]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(SCRAPING_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRAPING_ROOT))


@pytest.fixture
def scraping_fixture():
    return load_scraping_fixture

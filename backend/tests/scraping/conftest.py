import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRAPING = _HERE.parents[1] / "scraping"
for _p in (_HERE, _SCRAPING):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

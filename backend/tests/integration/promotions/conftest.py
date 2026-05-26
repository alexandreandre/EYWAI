"""Mock WeasyPrint pour collecte des tests d'intégration promotions."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

if "weasyprint" not in sys.modules:
    _mock = MagicMock()
    sys.modules["weasyprint"] = _mock
    sys.modules["weasyprint.HTML"] = MagicMock()

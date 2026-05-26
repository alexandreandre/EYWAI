"""
Fixtures locales du module promotions.

Mock WeasyPrint avant l'import de l'app (libs système optionnelles en local).
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

if "weasyprint" not in sys.modules:
    _mock_weasyprint = MagicMock()
    sys.modules["weasyprint"] = _mock_weasyprint
    sys.modules["weasyprint.HTML"] = MagicMock()

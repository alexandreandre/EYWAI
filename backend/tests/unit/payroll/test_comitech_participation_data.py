"""Contrôles données participation Comitech Composite 2025."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from comitech_participation_data import (  # noqa: E402
    COMITECH_PARTICIPATION_2025,
    PARTICIPATION_RSP,
)


def test_participation_2025_totals_match_quadra():
    gross_total = round(sum(r.gross_amount for r in COMITECH_PARTICIPATION_2025), 2)
    advance_total = round(sum(r.advance_amount for r in COMITECH_PARTICIPATION_2025), 2)
    assert gross_total == PARTICIPATION_RSP
    assert advance_total == 8_750.0
    assert len(COMITECH_PARTICIPATION_2025) == 20

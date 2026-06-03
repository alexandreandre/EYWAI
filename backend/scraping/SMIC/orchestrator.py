#!/usr/bin/env python3
"""Orchestrateur SMIC — délégué au socle commun."""

import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.base_orchestrator import main_entry  # noqa: E402

from spec import SPEC  # noqa: E402

if __name__ == "__main__":
    main_entry(SPEC)

#!/usr/bin/env python3
"""Orchestrateur MANDATAIRE (IA mono-source, human-gated)."""
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.base_orchestrator import main_entry
from spec import SPEC

if __name__ == "__main__":
    main_entry(SPEC)

#!/usr/bin/env python3
"""Retire alertes_baremes / alertes_maintien de tous les bulletins existants."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from app.modules.payslips.infrastructure.anomaly_cleanup import (
    purge_all_engine_alerts_from_payslips,
)


def main() -> int:
    count = purge_all_engine_alerts_from_payslips()
    print(f"Bulletins nettoyés : {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

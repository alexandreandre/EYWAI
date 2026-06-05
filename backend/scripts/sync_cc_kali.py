#!/usr/bin/env python3
"""Synchronisation mensuelle des conventions collectives depuis Légifrance (KALI)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def main() -> int:
    from app.modules.collective_agreements.application.kali_import import (
        get_kali_import_service,
    )
    from app.modules.collective_agreements.application.commands import (
        _kali_batch_to_dict,
    )

    outcomes = get_kali_import_service().sync_active_catalog(extract_rules=True)
    summary = _kali_batch_to_dict(outcomes)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

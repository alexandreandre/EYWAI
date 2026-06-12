#!/usr/bin/env python3
"""Exécute les exports planifiés (canaux compta/banque + RH par type) échus."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def main() -> int:
    from app.modules.exports.application.scheduled_exports import (
        run_due_channel_schedules,
        run_due_rh_schedules,
    )

    from app.modules.accounting_integration.application import service as accounting_service

    channel_results = run_due_channel_schedules()
    rh_results = run_due_rh_schedules()
    poll_stats = accounting_service.poll_pending_accounting_transmissions()
    results = channel_results + rh_results
    summary = {
        "executed": len(results),
        "success": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
        "channel_results": channel_results,
        "rh_results": rh_results,
        "accounting_poll": poll_stats,
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

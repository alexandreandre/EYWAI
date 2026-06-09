#!/usr/bin/env python3
"""Envoie les relances RH d'échéances (CDD, période d'essai, titre de séjour)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def main() -> int:
    from app.core.database import supabase
    from app.modules.notifications.application.hr_deadline_reminders import (
        send_hr_deadline_reminders,
    )

    companies_resp = (
        supabase.table("companies").select("id, company_name").eq("is_active", True).execute()
    )
    companies = list(companies_resp.data or [])

    results = []
    total_sent = 0
    total_errors = 0
    for company in companies:
        company_id = str(company.get("id") or "")
        if not company_id:
            continue
        outcome = send_hr_deadline_reminders(company_id)
        total_sent += int(outcome.get("sent", 0))
        total_errors += int(outcome.get("errors", 0))
        if outcome.get("sent") or outcome.get("skipped"):
            results.append(
                {
                    "company_id": company_id,
                    "company_name": company.get("company_name"),
                    **outcome,
                }
            )

    summary = {
        "companies_processed": len(companies),
        "total_sent": total_sent,
        "total_errors": total_errors,
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

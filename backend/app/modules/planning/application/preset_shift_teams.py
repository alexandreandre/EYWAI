"""Preset RH — postes équipes 3×8 industriel (paramétrable après création)."""

from __future__ import annotations

from typing import Any

from app.modules.planning.application import shift_type_commands
from app.modules.planning.application.queries import get_shift_types_for_company

INDUSTRIAL_3X8_SHIFT_TYPES: list[dict[str, Any]] = [
    {
        "code": "MATIN",
        "label": "Matin",
        "color": "#22c55e",
        "default_start": "04:00",
        "default_end": "12:00",
        "allows_overnight": False,
        "meal_allowance_eligible": True,
        "paid_break_minutes": 20,
        "unpaid_break_minutes": 30,
        "night_windows": [],
    },
    {
        "code": "APREM",
        "label": "Après-midi",
        "color": "#3b82f6",
        "default_start": "12:00",
        "default_end": "20:00",
        "allows_overnight": False,
        "meal_allowance_eligible": True,
        "paid_break_minutes": 20,
        "unpaid_break_minutes": 30,
        "night_windows": [],
    },
    {
        "code": "NUIT",
        "label": "Nuit",
        "color": "#6366f1",
        "default_start": "20:00",
        "default_end": "04:00",
        "allows_overnight": True,
        "meal_allowance_eligible": True,
        "paid_break_minutes": 20,
        "unpaid_break_minutes": 30,
        "night_windows": [{"start": "20:00", "end": "04:00", "rate": 0.25}],
    },
]


def apply_industrial_3x8_preset(company_id: str) -> dict[str, Any]:
    """Crée les types de poste MATIN / APREM / NUIT s'ils n'existent pas."""
    existing_codes = {
        str(s.get("code") or "").upper() for s in get_shift_types_for_company(company_id)
    }
    created: list[str] = []
    skipped: list[str] = []
    for spec in INDUSTRIAL_3X8_SHIFT_TYPES:
        code = str(spec["code"]).upper()
        if code in existing_codes:
            skipped.append(code)
            continue
        shift_type_commands.create_shift_type(company_id, dict(spec))
        created.append(code)
        existing_codes.add(code)
    return {
        "created_shift_types": created,
        "skipped_existing": skipped,
    }

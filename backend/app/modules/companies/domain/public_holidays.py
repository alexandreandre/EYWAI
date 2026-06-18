"""
Règles métier — jours fériés légaux observés par l'entreprise (settings JSON).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

FRENCH_PUBLIC_HOLIDAY_IDS: frozenset[str] = frozenset(
    {
        "new_year",
        "easter_monday",
        "labor_day",
        "victory_day",
        "ascension",
        "whit_monday",
        "bastille_day",
        "assumption",
        "all_saints",
        "armistice",
        "christmas",
    }
)

LABOR_DAY_HOLIDAY_ID = "labor_day"

DEFAULT_OBSERVED_HOLIDAY_IDS: List[str] = sorted(FRENCH_PUBLIC_HOLIDAY_IDS)


def normalize_observed_holiday_ids(
    observed_ids: Optional[List[str]],
) -> List[str]:
    """Retourne les IDs valides, ordre canonique, 1er mai toujours inclus."""
    if not observed_ids:
        return list(DEFAULT_OBSERVED_HOLIDAY_IDS)

    allowed = {
        holiday_id
        for holiday_id in observed_ids
        if holiday_id in FRENCH_PUBLIC_HOLIDAY_IDS
    }
    allowed.add(LABOR_DAY_HOLIDAY_ID)
    return [holiday_id for holiday_id in DEFAULT_OBSERVED_HOLIDAY_IDS if holiday_id in allowed]


def validate_observed_holiday_ids(observed_ids: List[str]) -> None:
    unknown = [holiday_id for holiday_id in observed_ids if holiday_id not in FRENCH_PUBLIC_HOLIDAY_IDS]
    if unknown:
        raise ValueError(
            "Identifiants de jours fériés invalides : "
            + ", ".join(sorted(set(unknown)))
        )


def merge_public_holidays_settings(
    current_settings: Dict[str, Any],
    public_holidays_delta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Fusionne public_holidays dans settings (observed_holiday_ids normalisés)."""
    if public_holidays_delta is None:
        return current_settings

    current_public = dict(current_settings.get("public_holidays") or {})
    if "observed_holiday_ids" in public_holidays_delta:
        raw_ids = public_holidays_delta.get("observed_holiday_ids")
        if raw_ids is None:
            current_public.pop("observed_holiday_ids", None)
        else:
            if not isinstance(raw_ids, list):
                raise ValueError("observed_holiday_ids doit être une liste.")
            validate_observed_holiday_ids([str(h) for h in raw_ids])
            current_public["observed_holiday_ids"] = normalize_observed_holiday_ids(
                [str(h) for h in raw_ids]
            )

    if current_public:
        current_settings["public_holidays"] = current_public
    else:
        current_settings.pop("public_holidays", None)

    return current_settings

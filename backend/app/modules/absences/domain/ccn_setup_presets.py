"""Presets de paramétrage entreprise par IDCC (onboarding import).

Les valeurs sont des défauts produit réutilisables — pas des exceptions par filiale.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# Clés alignées sur company_leave_settings + modulation (subset onboarding).
LeavePreset = Dict[str, Any]
ModulationPreset = Dict[str, Any]

_DEFAULT_LEAVE: LeavePreset = {
    "cp_acquisition_days_per_month": 2.5,
    "cp_counting_unit": "ouvrable",
    "cp_reference_period_start_month": 6,
    "cp_carryover_enabled": False,
    "rtt_use_calendar_formula": False,
    "rtt_use_forfait_jours_formula": False,
    "rtt_annual_days": 10.0,
    "rtt_period_start_month": 1,
    "rtt_period_end_month": 12,
    "rtt_carryover_enabled": False,
    "rtt_year_end_reminder_enabled": False,
    "rtt_year_end_reminder_days_before": 15,
}

_DEFAULT_MODULATION: ModulationPreset = {
    "enabled": False,
    "hour_account_enabled": False,
    "recovery_absence_enabled": False,
}

# IDCC fréquents du groupe — extensible sans hardcode filiale.
CCN_LEAVE_PRESETS: Dict[str, LeavePreset] = {
    "1979": {
        **_DEFAULT_LEAVE,
        "cp_counting_unit": "ouvrable",
        "rtt_annual_days": 12.0,
    },
    "3245": {
        **_DEFAULT_LEAVE,
        "cp_counting_unit": "ouvrable",
        "rtt_annual_days": 10.0,
    },
    "1501": {
        **_DEFAULT_LEAVE,
        "cp_counting_unit": "ouvrable",
        "rtt_use_forfait_jours_formula": True,
        "rtt_annual_days": None,
    },
    "1486": {
        **_DEFAULT_LEAVE,
        "rtt_annual_days": 8.0,
    },
}

CCN_MODULATION_PRESETS: Dict[str, ModulationPreset] = {
    "1979": {"enabled": True, "hour_account_enabled": True, "recovery_absence_enabled": True},
    "3245": {"enabled": True, "hour_account_enabled": True, "recovery_absence_enabled": True},
}


def normalize_idcc(idcc: Optional[str]) -> str:
    return str(idcc or "").strip()


def get_leave_preset_for_idcc(idcc: Optional[str]) -> LeavePreset:
    key = normalize_idcc(idcc)
    if key in CCN_LEAVE_PRESETS:
        return dict(CCN_LEAVE_PRESETS[key])
    return dict(_DEFAULT_LEAVE)


def get_modulation_preset_for_idcc(idcc: Optional[str]) -> ModulationPreset:
    key = normalize_idcc(idcc)
    if key in CCN_MODULATION_PRESETS:
        return dict(CCN_MODULATION_PRESETS[key])
    return dict(_DEFAULT_MODULATION)

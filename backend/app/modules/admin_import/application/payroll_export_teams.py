"""Paramétrage équipes MOD/MOI pour l'import export paie."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.modules.companies.infrastructure.repository import company_repository
from app.modules.teams.infrastructure.repository import teams_repository

_MOD_MOI_TEAM_NAMES = frozenset({"MOD", "MOI"})
_SETTINGS_KEY = "payroll_export_mod_moi_teams"


def company_has_mod_moi_teams(company_id: str) -> bool:
    teams = teams_repository.get_teams_by_company(company_id)
    for team in teams:
        name = (team.get("name") or "").strip().upper()
        if name in _MOD_MOI_TEAM_NAMES:
            return True
    return False


def resolve_mod_moi_team_mapping(
    company_id: str,
    *,
    explicit: Optional[bool] = None,
) -> bool:
    """Indique si la colonne Service doit être mappée vers les équipes MOD/MOI."""
    if explicit is not None:
        return bool(explicit)

    settings = company_repository.get_settings(company_id) or {}
    if _SETTINGS_KEY in settings:
        return bool(settings[_SETTINGS_KEY])

    return company_has_mod_moi_teams(company_id)


def mod_moi_team_mapping_info(company_id: str) -> Dict[str, Any]:
    default = resolve_mod_moi_team_mapping(company_id)
    return {
        "mod_moi_team_mapping": default,
        "mod_moi_team_mapping_default": default,
    }

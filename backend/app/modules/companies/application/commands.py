"""
Commandes (cas d'usage écriture) du module companies.

Délégation au repository. Vérification RH à faire côté appelant (api).
Comportement identique à l'ancien routeur api/routers/company.py.
"""
from __future__ import annotations

from typing import Any, Dict

from app.modules.companies.application.dto import CompanySettingsResultDto
from app.modules.companies.infrastructure.repository import company_repository


def update_company_settings(
    company_id: str,
    settings_delta: Dict[str, Any],
    current_user: Any,
) -> CompanySettingsResultDto:
    """
    Met à jour les paramètres de l'entreprise (merge avec settings existants).
    L'appelant doit vérifier has_rh_access_in_company(company_id).
    """
    current = company_repository.get_settings(company_id)
    if current is None:
        raise LookupError("Entreprise non trouvée.")

    current_settings = dict(current)
    if "medical_follow_up_enabled" in settings_delta:
        current_settings["medical_follow_up_enabled"] = bool(
            settings_delta["medical_follow_up_enabled"]
        )

    company_repository.update_settings(company_id, current_settings)
    return CompanySettingsResultDto(
        medical_follow_up_enabled=bool(current_settings.get("medical_follow_up_enabled")),
        settings=current_settings,
    )

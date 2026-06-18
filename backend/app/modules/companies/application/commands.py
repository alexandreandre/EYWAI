"""
Commandes (cas d'usage écriture) du module companies.

Délégation au repository. Vérification RH à faire côté appelant (api).
Comportement identique à l'ancien routeur api/routers/company.py.
"""

from __future__ import annotations

from typing import Any, Dict

from app.modules.companies.application.dto import CompanySettingsResultDto
from app.modules.companies.domain.public_holidays import merge_public_holidays_settings
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

    if "public_holidays" in settings_delta:
        try:
            current_settings = merge_public_holidays_settings(
                current_settings,
                settings_delta.get("public_holidays"),
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    company_repository.update_settings(company_id, current_settings)
    return CompanySettingsResultDto(
        medical_follow_up_enabled=bool(
            current_settings.get("medical_follow_up_enabled")
        ),
        settings=current_settings,
    )


def update_company_details(
    company_id: str,
    update_data: Dict[str, Any],
    current_user: Any,
) -> Dict[str, Any]:
    """
    Met à jour les champs administratifs de l'entreprise active.
    L'appelant doit vérifier has_rh_access_in_company(company_id).
    """
    if not update_data:
        row = company_repository.get_by_id(company_id)
        if not row:
            raise LookupError("Entreprise non trouvée.")
        return row

    updated = company_repository.update_company(company_id, update_data)
    if not updated:
        raise LookupError("Entreprise non trouvée.")
    return updated

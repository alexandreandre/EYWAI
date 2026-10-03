"""
Commandes (cas d'usage écriture) du module companies.

Délégation au repository. Vérification RH à faire côté appelant (api).
Comportement identique à l'ancien routeur api/routers/company.py.
"""

from __future__ import annotations

from typing import Any, Dict

from app.modules.audit.infrastructure.repository import audit_repository
from app.modules.companies.application.dto import CompanySettingsResultDto
from app.modules.companies.domain.parametres_paie import (
    changements,
    changements_settings,
    fusionner_reglages,
    separer_reglages,
)
from app.modules.companies.domain.public_holidays import merge_public_holidays_settings
from app.modules.employees.domain.trial_period_bareme import (
    validate_trial_period_settings,
)
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

    if "periode_essai" in settings_delta:
        current_settings["periode_essai"] = validate_trial_period_settings(
            settings_delta.get("periode_essai")
        )

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
    Met à jour les champs administratifs et les paramètres de paie de
    l'entreprise active. L'appelant doit vérifier has_rh_access_in_company(company_id).

    Les réglages rangés dans `settings` (taux d'assurance chômage, date de
    paiement, journée de solidarité) y sont fusionnés sans toucher aux autres
    clés ; `None` retire la clé. Seuls les champs qui changent vraiment sont
    écrits, et chacun laisse une trace d'audit avant/après.
    """
    avant = company_repository.get_by_id(company_id)
    if not avant:
        raise LookupError("Entreprise non trouvée.")
    if not update_data:
        return avant

    colonnes, reglages = separer_reglages(update_data)
    diff = changements(avant, colonnes)
    a_ecrire = {cle: colonnes[cle] for cle in diff}
    if reglages:
        settings = fusionner_reglages(avant.get("settings"), reglages)
        diff_settings = changements_settings(avant.get("settings"), settings)
        if diff_settings:
            a_ecrire["settings"] = settings
            diff.update(diff_settings)
    if not diff:
        return avant

    updated = company_repository.update_company(company_id, a_ecrire)
    if not updated:
        raise LookupError("Entreprise non trouvée.")
    audit_repository.log(
        company_id,
        str(getattr(current_user, "id", "") or "") or None,
        getattr(current_user, "email", None),
        "company.update",
        "company",
        company_id,
        {"changements": diff},
    )
    return updated

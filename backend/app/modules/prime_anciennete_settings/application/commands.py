"""Écriture des surcharges prime d'ancienneté (companies.settings)."""

from __future__ import annotations

from typing import Any

from app.modules.companies.infrastructure.repository import company_repository
from app.modules.prime_anciennete_settings.application import queries
from app.modules.prime_anciennete_settings.schemas.requests import (
    PrimeAncienneteSettingsUpdate,
)
from app.modules.prime_anciennete_settings.schemas.responses import (
    PrimeAncienneteSettings,
)


def _merge_overrides(
    current: dict[str, Any],
    update: PrimeAncienneteSettingsUpdate,
) -> dict[str, Any]:
    merged = dict(current)
    fields = update.model_dump(exclude_unset=True)
    for key, value in fields.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged


def save_prime_anciennete_settings(
    company_id: str,
    data: PrimeAncienneteSettingsUpdate,
) -> PrimeAncienneteSettings:
    company = company_repository.get_by_id(company_id)
    if not company:
        raise LookupError("Entreprise non trouvée.")

    settings = dict(company.get("settings") or {})
    pp = dict(settings.get("parametres_paie") or {})
    current_overrides = queries._read_overrides(settings)
    pp["prime_anciennete"] = _merge_overrides(current_overrides, data)
    settings["parametres_paie"] = pp
    company_repository.update_settings(company_id, settings)
    return queries.get_prime_anciennete_settings(company_id)

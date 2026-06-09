"""Commandes d'écriture paramétrage JEI."""

from __future__ import annotations

from typing import Any, Dict

from app.modules.jei_settings.application import queries
from app.modules.jei_settings.infrastructure.repository import jei_settings_repository
from app.modules.jei_settings.schemas.requests import JeiSettingsUpdate
from app.modules.jei_settings.schemas.responses import JeiSettings

_DB_WRITABLE_KEYS = frozenset(
    {
        "jei_enabled",
        "date_creation_etablissement",
        "taux_exoneration",
    }
)


def save_jei_settings(company_id: str, data: JeiSettingsUpdate) -> JeiSettings:
    """Fusionne avec l'existant et upsert."""
    current = queries.get_jei_settings(company_id)
    merged: Dict[str, Any] = current.model_dump(mode="json")
    patch = data.model_dump(exclude_unset=True)
    merged.update(patch)

    if merged.get("jei_enabled") and not merged.get("date_creation_etablissement"):
        raise ValueError(
            "La date de création de l'établissement est requise lorsque le statut JEI est activé."
        )

    payload = {k: merged[k] for k in _DB_WRITABLE_KEYS if k in merged}
    row = jei_settings_repository.upsert(company_id, payload)
    saved = JeiSettings.model_validate(row)
    fin, restantes = queries._eligibilite_dates(saved.date_creation_etablissement)
    saved.date_fin_eligibilite = fin
    saved.annees_restantes = restantes
    return saved

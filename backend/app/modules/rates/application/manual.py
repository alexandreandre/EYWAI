"""
Saisie manuelle d'un taux par un administrateur plateforme.

Versionne un bloc config_data complet via le port d'écriture (IRatesWriter),
en réutilisant la stratégie de versioning immuable de payroll_config.
Aucune logique de scraping : c'est une écriture directe, tracée et réservée
aux administrateurs plateforme.
"""

from __future__ import annotations

from typing import Any

from app.modules.rates.domain.interfaces import IRatesWriter


def apply_manual_rate_override(
    writer: IRatesWriter,
    *,
    config_key: str,
    config_data: dict[str, Any],
    actor_label: str,
    comment: str | None = None,
    source_links: list[str] | None = None,
) -> dict[str, Any]:
    """
    Applique une saisie manuelle d'un taux et retourne le résultat de versioning.

    Lève ValueError si le config_key est vide ou si config_data n'est pas un objet.
    """
    key = (config_key or "").strip()
    if not key:
        raise ValueError("Le paramètre config_key est obligatoire.")
    if not isinstance(config_data, dict) or not config_data:
        raise ValueError("config_data doit être un objet non vide.")

    note = (comment or "").strip()
    final_comment = (
        f"Saisie manuelle ({actor_label})" if not note
        else f"Saisie manuelle ({actor_label}) — {note}"
    )

    return writer.save_manual_version(
        config_key=key,
        new_config_data=config_data,
        comment=final_comment,
        source_links=source_links or [],
    )

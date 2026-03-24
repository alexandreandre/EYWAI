# Règles métier pures exports (sans FastAPI, sans infrastructure).
# Comportement strictement identique aux vérifications de l'ancien router.
from typing import Any, Dict


def is_supported_export_type_for_preview(export_type: str) -> bool:
    """Vrai si le type d'export est supporté pour la prévisualisation."""
    from .value_objects import EXPORT_TYPES_PREVIEW
    return export_type in EXPORT_TYPES_PREVIEW


def is_supported_export_type_for_generate(export_type: str) -> bool:
    """Vrai si le type d'export est supporté pour la génération."""
    from .value_objects import EXPORT_TYPES_GENERATE
    return export_type in EXPORT_TYPES_GENERATE


def validate_dsn_can_generate(
    preview_data: Dict[str, Any],
    accept_warnings: bool,
) -> None:
    """
    Vérifie que la DSN peut être générée (anomalies bloquantes, avertissements acceptés).
    Lève ValueError avec le message approprié si la génération est interdite.
    Comportement identique aux HTTPException 400 du router DSN.
    """
    anomalies = preview_data.get("anomalies") or []
    blocking = [a for a in anomalies if a.get("severity") == "blocking"]
    if blocking:
        raise ValueError(
            f"Impossible de générer la DSN : {len(blocking)} anomalie(s) bloquante(s) détectée(s)"
        )
    warnings = preview_data.get("warnings") or []
    if warnings and not accept_warnings:
        raise ValueError(
            "Des avertissements sont présents. Vous devez les accepter explicitement pour générer la DSN."
        )

"""Confinement temporaire de l'accès aux données RH du Copilot."""

import os


COPILOT_DATA_UNAVAILABLE_MESSAGE = (
    "Les questions portant sur les données RH sont temporairement indisponibles "
    "pendant une mise à niveau de sécurité. L'aide sur EYWAI et les conventions "
    "collectives reste disponible."
)


class DataRetrievalDisabledError(RuntimeError):
    """Signale que la récupération de données RH est désactivée."""


def is_rh_data_enabled() -> bool:
    """Retourne vrai uniquement lorsque l'activation est explicite."""
    return os.getenv("COPILOT_RH_DATA_ENABLED", "false").strip().lower() == "true"

"""
Lifecycle de l'application : startup et shutdown.

Fonctions à enregistrer sur l'app FastAPI (on_event ou lifespan).
Implémentation minimale : log uniquement ; à étendre (pool DB, caches, etc.) sans impact métier.
"""
from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger(__name__)


async def on_startup() -> None:
    """Appelé au démarrage de l'application."""
    logger.info("Application startup")


async def on_shutdown() -> None:
    """Appelé à l'arrêt de l'application."""
    logger.info("Application shutdown")


def register_lifecycle(app) -> None:
    """
    Enregistre les hooks startup/shutdown sur l'instance FastAPI.
    Usage dans app/main.py : register_lifecycle(app)
    """
    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)

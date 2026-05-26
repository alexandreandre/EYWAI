"""
Lifecycle de l'application : startup et shutdown (lifespan FastAPI).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Hook de démarrage / arrêt (remplace les anciens on_event / add_event_handler)."""
    configure_logging()
    logger.info("Application startup")
    try:
        yield
    finally:
        logger.info("Application shutdown")


def register_lifecycle(app: FastAPI) -> None:
    """
    Compat : le lifespan doit être passé au constructeur FastAPI.
    Si l'app a été créée sans lifespan, on ne peut pas le rattacher après coup.
    """
    if getattr(app, "router", None) and getattr(app.router, "lifespan_context", None):
        return
    logger.warning(
        "lifespan non attaché : passer lifespan=app.core.lifecycle.lifespan à FastAPI()"
    )

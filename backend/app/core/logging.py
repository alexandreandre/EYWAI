"""
Configuration du logging pour l'application.

Logger unique pour app.core ; format et niveau configurables.
Aucun impact sur les print() existants ; à brancher progressivement.
"""
from __future__ import annotations

import logging
import sys

# Nom du logger racine de l'app
LOGGER_NAME = "app"

# Niveau par défaut (surchargeable via env ou settings)
DEFAULT_LEVEL = logging.INFO


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Retourne un logger pour le module donné.
    Si name est None, retourne le logger racine 'app'.
    """
    return logging.getLogger(name or LOGGER_NAME)


def configure_logging(
    level: int = DEFAULT_LEVEL,
    format_string: str | None = None,
) -> None:
    """
    Configure le handler du logger racine (stream stdout).
    À appeler au startup si besoin ; sinon les loggers utilisent la config par défaut.
    """
    if format_string is None:
        format_string = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    root = logging.getLogger(LOGGER_NAME)
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter(format_string))
        root.addHandler(handler)

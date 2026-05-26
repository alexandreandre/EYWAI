"""
Configuration du logging pour l'application.

- Niveau global via LOG_LEVEL (défaut : WARNING en prod, INFO si APP_DEBUG).
- Traces verbeuses : APP_DEBUG (auth, sécurité, plannings…) ou PAYROLL_DEBUG (moteur paie).
- Shim print() de secours pour tout reliquat non migré.
"""

from __future__ import annotations

import builtins
import logging
import os
import sys
from typing import Any

from app.core.constants import (
    ENV_APP_DEBUG,
    ENV_LOG_LEVEL,
    ENV_PAYROLL_DEBUG,
)

LOGGER_NAME = "app"
DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

_STDERR_WARNING_MARKERS = (
    "ERREUR",
    "ERROR",
    "❌",
    "[WARNING]",
    "⚠",
    "WARN:",
    "Avertissement",
)
_STDERR_INFO_MARKERS = ("INFO:", "[SCRAPING]")

_ORIGINAL_PRINT = builtins.print
_print_shim_installed = False


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


def is_app_debug_enabled() -> bool:
    """Traces applicatives (auth, get_current_user, plannings, etc.)."""
    return _env_truthy(ENV_APP_DEBUG)


def is_payroll_debug_enabled() -> bool:
    """Traces moteur de paie (cotisations, bulletin, générateur…)."""
    return _env_truthy(ENV_PAYROLL_DEBUG)


def resolve_log_level() -> int:
    """Niveau racine : LOG_LEVEL explicite, sinon INFO si debug, sinon WARNING."""
    raw = os.getenv(ENV_LOG_LEVEL, "").strip().upper()
    if raw:
        return getattr(logging, raw, logging.WARNING)
    if is_app_debug_enabled() or is_payroll_debug_enabled():
        return logging.INFO
    return logging.WARNING


def get_logger(name: str | None = None) -> logging.Logger:
    """Logger sous l'arborescence ``app`` (ex. ``app.modules.auth``)."""
    if name and not name.startswith(f"{LOGGER_NAME}.") and name != LOGGER_NAME:
        name = f"{LOGGER_NAME}.{name.removeprefix('app.')}"
    return logging.getLogger(name or LOGGER_NAME)


def log_app_debug(logger: logging.Logger, msg: str, *args: Any) -> None:
    """Trace verbose réservée au dev applicatif (``APP_DEBUG=1``)."""
    if is_app_debug_enabled():
        logger.debug(msg, *args)


def log_payroll_debug(logger: logging.Logger, msg: str, *args: Any) -> None:
    """Trace verbose moteur de paie (``PAYROLL_DEBUG=1``)."""
    if is_payroll_debug_enabled():
        logger.debug(msg, *args)


def _message_from_args(*args: Any) -> str:
    return " ".join(str(a) for a in args)


def _legacy_print_level(message: str, *, to_stderr: bool) -> int:
    upper = message.upper()
    if any(marker in message or marker in upper for marker in _STDERR_WARNING_MARKERS):
        return logging.WARNING
    if to_stderr and any(marker in message for marker in _STDERR_INFO_MARKERS):
        return logging.INFO
    if to_stderr:
        return logging.DEBUG
    return logging.DEBUG


def _should_emit_legacy_print(message: str, *, to_stderr: bool) -> bool:
    level = _legacy_print_level(message, to_stderr=to_stderr)
    if level >= logging.WARNING:
        return True
    if to_stderr and is_payroll_debug_enabled():
        return True
    if is_app_debug_enabled():
        return True
    return False


def _legacy_print(*args: Any, **kwargs: Any) -> None:
    """Remplace builtins.print pour les print() non migrés."""
    file = kwargs.get("file")
    to_stderr = file is sys.stderr
    message = _message_from_args(*args)
    if not _should_emit_legacy_print(message, to_stderr=to_stderr):
        return

    level = _legacy_print_level(message, to_stderr=to_stderr)
    logger_name = (
        f"{LOGGER_NAME}.payroll"
        if to_stderr and is_payroll_debug_enabled()
        else LOGGER_NAME
    )
    logging.getLogger(logger_name).log(level, message)


def install_legacy_print_shim() -> None:
    global _print_shim_installed
    if _print_shim_installed:
        return
    builtins.print = _legacy_print
    _print_shim_installed = True


def _quiet_noisy_libraries(level: int) -> None:
    for name in (
        "httpx",
        "httpcore",
        "hpack",
        "openai",
        "urllib3",
        "google",
        "google.auth",
        "googleapiclient",
        "watchfiles",
        "multipart",
        "charset_normalizer",
    ):
        logging.getLogger(name).setLevel(max(level, logging.WARNING))


def configure_logging(
    level: int | None = None,
    format_string: str | None = None,
) -> None:
    """
    Configure le handler stdout du logger racine ``app`` et les niveaux utiles.
    Idempotent : safe à rappeler au startup.
    """
    level = level if level is not None else resolve_log_level()
    fmt = format_string or DEFAULT_FORMAT

    app_logger = logging.getLogger(LOGGER_NAME)
    app_logger.setLevel(level)
    app_logger.propagate = False

    if not app_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter(fmt))
        app_logger.addHandler(handler)

    for handler in app_logger.handlers:
        handler.setLevel(level)

    root = logging.getLogger()
    if not root.handlers:
        root_handler = logging.StreamHandler(sys.stdout)
        root_handler.setFormatter(logging.Formatter(fmt))
        root.addHandler(root_handler)
    root.setLevel(level)

    logging.getLogger("uvicorn.error").setLevel(level)
    access_level = logging.INFO if is_app_debug_enabled() else logging.WARNING
    logging.getLogger("uvicorn.access").setLevel(access_level)

    _quiet_noisy_libraries(level)
    install_legacy_print_shim()

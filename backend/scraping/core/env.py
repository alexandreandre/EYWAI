"""Chargement .env pour les scripts de scraping."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

SCRAPING_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = SCRAPING_ROOT.parent
REPO_ROOT = BACKEND_ROOT.parent


def load_env() -> Path | None:
    """Charge le premier .env trouvé (backend/ ou racine monorepo)."""
    for candidate in [
        BACKEND_ROOT / ".env",
        REPO_ROOT / ".env",
        Path.cwd() / ".env",
    ]:
        if candidate.exists():
            load_dotenv(candidate)
            return candidate
    return None


def ensure_scraping_path() -> None:
    """Ajoute backend/scraping au sys.path pour imports utils/cotisation_sync."""
    import sys

    root = str(SCRAPING_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)

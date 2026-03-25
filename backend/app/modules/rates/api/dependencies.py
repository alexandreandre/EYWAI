"""
Dépendances API pour le module rates.

Fournit le reader (implémentation du port IAllRatesReader) pour injection dans les routes.
"""

from __future__ import annotations

from app.modules.rates.domain.interfaces import IAllRatesReader
from app.modules.rates.infrastructure.repository import SupabaseAllRatesReader

_reader: SupabaseAllRatesReader | None = None


def get_all_rates_reader() -> IAllRatesReader:
    """Retourne le reader des configs taux (lignes brutes, singleton par défaut)."""
    global _reader
    if _reader is None:
        _reader = SupabaseAllRatesReader()
    return _reader

"""
Dépendances API pour le module rates.

Fournit le reader (implémentation du port IAllRatesReader) pour injection dans les routes.
"""

from __future__ import annotations

from app.modules.rates.domain.interfaces import IAllRatesReader, IRatesWriter
from app.modules.rates.infrastructure.repository import (
    SupabaseAllRatesReader,
    SupabaseRatesWriter,
)

_reader: SupabaseAllRatesReader | None = None
_writer: SupabaseRatesWriter | None = None


def get_all_rates_reader() -> IAllRatesReader:
    """Retourne le reader des configs taux (lignes brutes, singleton par défaut)."""
    global _reader
    if _reader is None:
        _reader = SupabaseAllRatesReader()
    return _reader


def get_rates_writer() -> IRatesWriter:
    """Retourne le writer des configs taux (saisie manuelle versionnée)."""
    global _writer
    if _writer is None:
        _writer = SupabaseRatesWriter()
    return _writer

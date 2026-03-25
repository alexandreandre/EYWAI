"""
Résultat d'opération sans exception (Success / Failure).

Utile pour les cas d'usage qui veulent retourner un succès ou une erreur
sans lever, puis convertir en HTTP en couche API. Minimal, sans dépendance métier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True)
class Ok(Generic[T]):
    """Opération réussie."""

    value: T


@dataclass(frozen=True)
class Err(Generic[E]):
    """Opération en échec (message ou détail)."""

    error: E


# Union pour type hints
Result = Ok[T] | Err[E]


def is_ok(r: Result[T, E]) -> bool:
    """Retourne True si le résultat est Ok."""
    return isinstance(r, Ok)


def is_err(r: Result[T, E]) -> bool:
    """Retourne True si le résultat est Err."""
    return isinstance(r, Err)

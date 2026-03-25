"""
Types et alias communs pour les modules.

Pas de logique métier ; uniquement des définitions réutilisables
(alias, TypeVar) pour garder la cohérence.
"""

from __future__ import annotations

from typing import TypeVar

# Identifiants : en API on manipule souvent des UUID en string
UUID_STR = str

# Type générique pour les entités/DTOs partagés
T = TypeVar("T")

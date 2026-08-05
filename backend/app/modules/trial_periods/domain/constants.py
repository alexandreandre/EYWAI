"""Statuts d'une période d'essai, alignés sur la contrainte CHECK de la table."""

from __future__ import annotations

STATUS_EN_COURS = "en_cours"
STATUS_CONFIRMEE = "confirmee"
STATUS_ROMPUE = "rompue"

VALID_STATUSES = frozenset({STATUS_EN_COURS, STATUS_CONFIRMEE, STATUS_ROMPUE})

__all__ = [
    "STATUS_CONFIRMEE",
    "STATUS_EN_COURS",
    "STATUS_ROMPUE",
    "VALID_STATUSES",
]

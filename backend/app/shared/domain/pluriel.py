"""Accord en nombre des textes montrés à l'écran (« 1 jour », « 2 jours »)."""

from __future__ import annotations


def accord(n: float, un: str, plusieurs: str | None = None) -> str:
    """Le mot seul, accordé au nombre : « validé » à 0 et 1, « validés » dès 2."""
    return un if n < 2 else (plusieurs or un + "s")


def pluriel(n: float, un: str, plusieurs: str | None = None) -> str:
    """« 1 jour » / « 2 jours » : le pluriel dès 2, comme en français (0 est singulier)."""
    return f"{n} {un if n < 2 else (plusieurs or un + 's')}"

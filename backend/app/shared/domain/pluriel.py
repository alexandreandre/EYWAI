"""Accord en nombre des textes montrés à l'écran (« 1 jour », « 2 jours »)."""

from __future__ import annotations


def pluriel(n: int, un: str, plusieurs: str | None = None) -> str:
    """« 1 jour » / « 2 jours » : le pluriel dès 2, comme en français (0 est singulier)."""
    return f"{n} {un if n < 2 else (plusieurs or un + 's')}"

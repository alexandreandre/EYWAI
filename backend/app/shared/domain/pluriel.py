"""Accord en nombre des textes montrés à l'écran (« 1 jour », « 2 jours »)."""

from __future__ import annotations


def accord(n: float, un: str, plusieurs: str | None = None) -> str:
    """Le mot seul, accordé au nombre : « validé » à 0 et 1, « validés » dès 2."""
    return un if n < 2 else (plusieurs or un + "s")


def pluriel(n: float, un: str, plusieurs: str | None = None) -> str:
    """« 1 jour » / « 2 jours » : le pluriel dès 2, comme en français (0 est singulier)."""
    return f"{n} {un if n < 2 else (plusieurs or un + 's')}"


MOIS_FR = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)


def de_mois(month: int) -> str:
    """« de mars », « d'octobre » : le mois avec sa préposition élidée."""
    nom = MOIS_FR[month - 1]
    return f"d'{nom}" if nom[0] in "aeiouéè" else f"de {nom}"


def phrase_jours_a_completer(nb: int, month: int, debut, fin) -> str:
    """Début commun du contrôle avant paie et du refus de génération (26/11) :
    « 2 jours à compléter pour la paie d'octobre (période du 21/09 au 25/10) »."""
    return (
        f"{pluriel(nb, 'jour')} à compléter pour la paie {de_mois(month)} "
        f"(période du {debut:%d/%m} au {fin:%d/%m})"
    )

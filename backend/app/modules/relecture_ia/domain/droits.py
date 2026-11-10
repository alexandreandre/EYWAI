"""Qui peut lancer la relecture : une liste d'e-mails, réglable sans déploiement du code."""

from __future__ import annotations

COMPTES_PAR_DEFAUT = "eandre@maji-invest.fr"


def compte_autorise(email: str | None, liste: str | None) -> bool:
    """`liste` : la valeur de RELECTURE_IA_COMPTES (e-mails séparés par des virgules). Vide : le compte par défaut."""
    adresse = (email or "").strip().lower()
    if not adresse:
        return False
    source = liste if liste and liste.strip() else COMPTES_PAR_DEFAUT
    return adresse in {c.strip().lower() for c in source.split(",") if c.strip()}

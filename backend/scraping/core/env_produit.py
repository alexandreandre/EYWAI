"""Lecture des variables d'environnement du produit.

Les variables s'appellent MARTINE_<SUFFIXE>. Repli sur l'ancien préfixe, pour
que la configuration déjà posée (Cloud Run, workflows) continue de marcher.
"""
from __future__ import annotations

import os

_PREFIXE = "MARTINE_"
_ANCIEN_PREFIXE = "EYWAI_"


def lire_env(nom: str, defaut: str | None = None) -> str | None:
    """Valeur de ``nom`` (MARTINE_X), sinon de l'ancienne variable EYWAI_X, sinon ``defaut``."""
    valeur = os.environ.get(nom)
    if valeur is not None:
        return valeur
    if nom.startswith(_PREFIXE):
        valeur = os.environ.get(_ANCIEN_PREFIXE + nom[len(_PREFIXE):])
        if valeur is not None:
            return valeur
    return defaut

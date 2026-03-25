"""
Utilitaires de chaînes de caractères partagés.
"""

import unicodedata


def remove_accents(text: str) -> str:
    """
    Enlève tous les accents d'une chaîne de caractères.

    Utilisé pour créer des noms de fichiers et dossiers compatibles
    avec tous les systèmes d'exploitation et éviter les problèmes d'encodage.

    Exemples:
        >>> remove_accents("Léo")
        'Leo'
        >>> remove_accents("José")
        'Jose'

    Args:
        text: Texte contenant potentiellement des accents

    Returns:
        Texte sans accents
    """
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")

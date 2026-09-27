"""Le manifeste d'accès réel vit hors git : il nomme des personnes (dépôt public).

Les tests qui le vérifient lisent `data/_acces/access_manifest.json` sur le
poste et se mettent en attente ailleurs (CI). Ils tirent l'identité d'une
personne du manifeste lui-même, pour qu'aucun nom réel ne soit écrit ici.
"""

from __future__ import annotations

from pathlib import Path

import pytest

MANIFESTE_REEL = Path(__file__).resolve().parents[4] / "data/_acces/access_manifest.json"

exige_manifeste_reel = pytest.mark.skipif(
    not MANIFESTE_REEL.exists(),
    reason="manifeste d'accès hors git (data/_acces/) : test local seulement",
)


def identite(manifest: dict, key: str) -> dict:
    """Prénom, nom, identifiant et adresse de la personne `key` du manifeste."""
    personne = next(p for p in manifest["people"] if p["key"] == key)
    ident = personne.get("identity") or {}
    prenom, _, nom = (ident.get("name") or "").partition(" ")
    username = ident.get("username") or f"{prenom}.{nom}".lower()
    email = ident.get("email") or f"{username}@exemple.test"
    return {"prenom": prenom, "nom": nom, "username": username, "email": email}

"""Comparer des intitulés de poste, entre collègues et avec les métiers de l'Insee."""

from __future__ import annotations

import re
import unicodedata
from typing import List

#: Mots sans poids dans un intitulé.
_VIDES = frozenset(
    "de du des d la le les l et en a au aux h f dont pour sur par".split()
)
#: Abréviations des intitulés repris de Quadra (coupés à 30 caractères).
_ABREVIATIONS = {
    "agt": "agent",
    "prod": "production",
    "qualif": "qualifie",
    "resp": "responsable",
    "ass": "assistant",
    "assist": "assistant",
    "assit": "assistant",
    "techni": "technicien",
    "app": "apprenti",
    "adj": "adjoint",
    "chaufeur": "chauffeur",
}
#: Féminin vers masculin, comme l'Insee nomme ses métiers.
_FEMININS = (("trice", "teur"), ("euse", "eur"), ("iere", "ier"), ("ienne", "ien"), ("ee", "e"))


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def normaliser_poste(texte: str) -> str:
    """Minuscules, sans accents ni ponctuation, espaces simples : « le même poste »."""
    s = _sans_accents(str(texte or "").lower())
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def est_cadre(statut: str) -> bool:
    mots = normaliser_poste(statut).split()
    return "cadre" in mots and "non" not in mots


def _mot(mot: str) -> str:
    mot = _ABREVIATIONS.get(mot, mot)
    if len(mot) > 4 and mot.endswith("s") and not mot.endswith("ss"):
        mot = mot[:-1]
    for fin, masculin in _FEMININS:
        if mot.endswith(fin) and len(mot) > len(fin) + 2:
            return mot[: -len(fin)] + masculin
    return mot


def mots_metier(texte: str) -> List[str]:
    """Les mots qui comptent, au masculin singulier, abréviations développées."""
    return [_mot(m) for m in normaliser_poste(texte).split() if m not in _VIDES]


def tete(metier: str) -> str:
    """Le métier sans ses précisions : ce qui précède la première virgule ou parenthèse."""
    return re.split(r"[,(]", metier, maxsplit=1)[0]

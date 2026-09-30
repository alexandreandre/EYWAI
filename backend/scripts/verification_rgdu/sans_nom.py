"""Garde : un fichier destiné à git ne contient aucun nom de salarié (table des pseudonymes)."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from functools import lru_cache

from scripts.verification_rgdu.chemins import DATA


def _norme(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()


@lru_cache(maxsize=1)
def _mots_interdits() -> frozenset[str]:
    table = json.loads((DATA / "_outils" / "pseudonymes.json").read_text(encoding="utf-8"))
    return frozenset(m for cle in table for m in _norme(cle).split() if len(m) >= 4)


def noms_trouves(texte: str) -> list[str]:
    t = _norme(texte)
    return sorted(m for m in _mots_interdits() if re.search(rf"\b{re.escape(m)}\b", t))


if __name__ == "__main__":
    fautes = {f: noms_trouves(open(f, encoding="utf-8").read()) for f in sys.argv[1:]}
    fautes = {f: n for f, n in fautes.items() if n}
    print(fautes or "aucun nom")
    sys.exit(1 if fautes else 0)

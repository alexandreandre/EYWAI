"""Les 430 codes PCS-ESE acceptés par la DSN, avec les métiers de l'Insee.

Liste : table DSN « PCSESE » P26V01 de net-entreprises (25/09/2025), 429 codes de la
PCS-ESE 2017 plus « 9999 » ; le cahier technique 2026.1.2 n'accepte qu'elle (CRE-11, p. 183)
et compte la casse (p. 88). Métiers : pages Insee de la PCS-ESE 2017 (mise à jour du
19/12/2025). Le fichier est construit par `scripts/pcs_ese/construire_referentiel.py`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Tuple

FICHIER = Path(__file__).resolve().parents[1] / "data" / "pcs_ese_2017.json"

#: Emplois exigeant des conditions d'aptitude particulières (Ecap) : guide OETH de l'Urssaf,
#: version 2.5 du 7 avril 2026, p. 22-23. L'Urssaf calcule leur effectif à partir du code
#: déclaré en DSN ; chaque Ecap ouvre une déduction de 17 fois le Smic horaire brut.
CODES_ECAP = frozenset(
    {
        "389b", "389c", "480b", "526e", "533a", "533b", "534a", "534b", "546a", "546d",
        "546e", "553b", "624d", "621a", "621b", "621c", "621e", "621g", "632a", "632c",
        "632e", "641a", "641b", "643a", "651a", "651b", "652b", "654b", "654c", "656b",
        "656c", "671c", "671d", "681a", "691a", "692a",
    }
)


@dataclass(frozen=True)
class Exclusion:
    libelle: str
    #: Les codes à prendre à la place (« voir 524b »).
    voir: Tuple[str, ...]


@dataclass(frozen=True)
class Rubrique:
    code: str
    libelle: str
    typiques: Tuple[str, ...]
    assimilees: Tuple[str, ...]
    exclues: Tuple[Exclusion, ...]
    #: Code ajouté pour les employeurs publics (suffixé « * » par l'Insee).
    public: bool
    ecap: bool

    @property
    def groupe(self) -> str:
        return self.code[:1]


@lru_cache(maxsize=1)
def charger_referentiel() -> Dict[str, Rubrique]:
    donnees = json.loads(FICHIER.read_text(encoding="utf-8"))
    return {
        r["code"]: Rubrique(
            code=r["code"],
            libelle=r["libelle"],
            typiques=tuple(r["typiques"]),
            assimilees=tuple(r["assimilees"]),
            exclues=tuple(Exclusion(e["libelle"], tuple(e["voir"])) for e in r["exclues"]),
            public=bool(r["public"]),
            ecap=r["code"] in CODES_ECAP,
        )
        for r in donnees["rubriques"]
    }


def code_valide(code: str) -> bool:
    """Le code est l'un des 430 de la table DSN, à la lettre près (minuscules comprises)."""
    return code in charger_referentiel()

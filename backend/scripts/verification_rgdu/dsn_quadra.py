"""DSN Quadra : SMIC retenu (S21.G00.79 type 01) et réduction (codes 018 + 106) par base brute."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from scripts.verification_rgdu.chemins import ANNEE, DATA, SOCIETES

LIGNE = re.compile(r"^(S\d\d\.G\d\d\.\d\d\.\d{3}),'(.*)'\s*$")


@dataclass
class BaseReduction:
    nir: str
    nom: str
    prenom: str
    debut: date
    fin: date
    assiette: float | None = None
    smic_retenu: float | None = None
    montant_018: float = 0.0
    montant_106: float = 0.0

    @property
    def reduction(self) -> float:
        return round(-(self.montant_018 + self.montant_106), 2)


def _date(s: str) -> date:
    return datetime.strptime(s, "%d%m%Y").date()


def lire_dsn(chemin: Path) -> list[BaseReduction]:
    bases: list[BaseReduction] = []
    individu = {"nir": "", "nom": "", "prenom": ""}
    type_base = composant = code = None
    periode: list[str] = []
    courante: BaseReduction | None = None
    for brute in chemin.read_bytes().decode("latin-1").splitlines():
        m = LIGNE.match(brute.strip())
        if not m:
            continue
        rub, val = m.groups()
        if rub == "S21.G00.30.001":
            individu = {"nir": val[:13], "nom": "", "prenom": ""}
            courante = None
        elif rub == "S21.G00.30.002":
            individu["nom"] = val
        elif rub == "S21.G00.30.004":
            individu["prenom"] = val
        elif rub == "S21.G00.78.001":
            type_base, periode, courante = val, [], None
        elif rub in ("S21.G00.78.002", "S21.G00.78.003"):
            periode.append(val)
            if type_base == "03" and len(periode) == 2:
                courante = BaseReduction(debut=_date(periode[0]), fin=_date(periode[1]), **individu)
                bases.append(courante)
        elif rub == "S21.G00.78.004" and courante is not None:
            courante.assiette = float(val)
        elif rub == "S21.G00.79.001":
            composant = val
        elif rub == "S21.G00.79.004" and courante is not None and composant == "01":
            courante.smic_retenu = float(val)
        elif rub == "S21.G00.81.001":
            code = val
        elif rub == "S21.G00.81.004" and courante is not None and code in ("018", "106"):
            if code == "018":
                courante.montant_018 += float(val)
            else:
                courante.montant_106 += float(val)
    return bases


def dsn_du_mois(societe: str, mois: int) -> list[BaseReduction]:
    chemin = DATA / SOCIETES[societe]["dossier"] / "dsn" / f"{ANNEE:04d}-{mois:02d}.dsn"
    return lire_dsn(chemin) if chemin.exists() else []

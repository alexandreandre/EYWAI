"""Reconstitue la nomenclature des codes de cotisation depuis les DSN du cabinet.

Le cabinet n'a pas fourni sa table « rubrique de paie → code DSN ». Les DSN
qu'il a déposées la contiennent pourtant en creux : chaque cotisation y porte
son code, son organisme, son assiette et son taux.

Ce script inventorie les codes réellement utilisés, société par société, et les
confronte à ceux que notre export sait produire
(`app.modules.dsn_export.domain.cotisation_mapping`). Ce qui reste dans la
colonne « inconnu du moteur » est exactement ce qu'il faut demander.

    venv/bin/python -m scripts.dsn_nomenclature_gap

Écrit un rapport dans `data/_dsn_conformance/`. Aucun contenu nominatif : le
script n'extrait que des codes, des taux et des organismes.
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import statistics
import sys
from typing import Dict, List, Optional, Set, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.modules.dsn_export.domain.cotisation_mapping import (  # noqa: E402
    CODE_TO_BASE,
    COTI_ID_TO_DSN_CODE,
    _LIBELLE_TO_CODE,
)
from app.modules.dsn_export.domain.nomenclature_cotisation import (  # noqa: E402
    libelle_cotisation,
)

# Blocs porteurs de codes normalisés. Les libellés sont ceux du cahier
# technique NEODeS ; un bloc dont le sens n'est pas certain reste sans libellé.
BLOCS = {
    "S21.G00.23.001": "Cotisation agrégée (établissement)",
    "S21.G00.78.001": "Base assujettie",
    "S21.G00.79.001": "Composant de base assujettie",
    "S21.G00.81.001": "Cotisation individuelle",
}

OPS_RUBRIQUE = "S21.G00.81.002"
ASSIETTE_RUBRIQUE = "S21.G00.81.003"
MONTANT_RUBRIQUE = "S21.G00.81.004"
TAUX_RUBRIQUE = "S21.G00.81.007"


def codes_connus_du_moteur() -> Set[str]:
    """Codes que notre export sait réellement émettre.

    `CODE_TO_BASE` est volontairement exclu : il ne fait qu'associer un code à
    sa base assujettie. Un code qui n'y figure que là n'est jamais produit,
    faute d'une rubrique de bulletin qui l'alimente.
    """
    codes = set(COTI_ID_TO_DSN_CODE.values())
    codes |= {code for _, code in _LIBELLE_TO_CODE}
    return {c.zfill(3) for c in codes}


def _val(raw: str) -> str:
    return raw.strip().strip("'")


class Observation:
    """Ce qu'on sait d'un code, tel qu'il apparaît dans les DSN réelles."""

    def __init__(self) -> None:
        self.occurrences = 0
        self.societes: Set[str] = set()
        self.mois: Set[str] = set()
        self.taux: List[float] = []
        self.ops: Set[str] = set()
        self.montants: List[float] = []

    def taux_observes(self) -> List[float]:
        arrondis = sorted({round(t, 3) for t in self.taux if t})
        return arrondis[:8]


def lire_dsn(chemin: pathlib.Path) -> List[Tuple[str, str]]:
    lignes: List[Tuple[str, str]] = []
    with chemin.open(encoding="latin-1") as fh:
        for ligne in fh:
            rubrique, _, valeur = ligne.strip().partition(",")
            if rubrique:
                lignes.append((rubrique.strip(), _val(valeur)))
    return lignes


def analyser(fichiers: List[pathlib.Path]) -> Dict[str, Dict[str, Observation]]:
    """{rubrique de code → {code → Observation}}"""
    resultat: Dict[str, Dict[str, Observation]] = {
        rub: collections.defaultdict(Observation) for rub in BLOCS
    }

    for chemin in fichiers:
        societe = chemin.parts[-3]
        mois = chemin.stem
        courant: Optional[Observation] = None

        for rubrique, valeur in lire_dsn(chemin):
            if rubrique in BLOCS:
                code = valeur.zfill(3) if rubrique != "S21.G00.78.001" else valeur.zfill(2)
                obs = resultat[rubrique][code]
                obs.occurrences += 1
                obs.societes.add(societe)
                obs.mois.add(mois)
                courant = obs if rubrique == "S21.G00.81.001" else None
                continue

            if courant is None:
                continue
            if rubrique == OPS_RUBRIQUE and valeur:
                courant.ops.add(valeur)
            elif rubrique == TAUX_RUBRIQUE:
                try:
                    courant.taux.append(float(valeur))
                except ValueError:
                    pass
            elif rubrique == MONTANT_RUBRIQUE:
                try:
                    courant.montants.append(float(valeur))
                except ValueError:
                    pass

    return resultat


def rapport(resultat: Dict[str, Dict[str, Observation]], fichiers: List[pathlib.Path]) -> str:
    connus = codes_connus_du_moteur()
    societes = sorted({c.parts[-3] for c in fichiers})
    mois = sorted({c.stem for c in fichiers})

    out: List[str] = []
    out.append("# Nomenclature DSN reconstituée depuis les déclarations du cabinet")
    out.append("")
    out.append(
        f"Source : **{len(fichiers)} DSN**, {len(societes)} sociétés "
        f"({', '.join(societes)}), de {mois[0]} à {mois[-1]}."
    )
    out.append("")
    out.append(
        "Un code marqué **inconnu** n'est pas produit par notre export : c'est "
        "une cotisation que le cabinet déclare et que nous ne saurions pas "
        "coder. C'est la liste à faire confirmer."
    )
    out.append("")

    for rubrique, libelle in BLOCS.items():
        obs_par_code = resultat[rubrique]
        if not obs_par_code:
            continue
        inconnus = [c for c in obs_par_code if rubrique == "S21.G00.81.001" and c not in connus]
        out.append(f"## {libelle} — `{rubrique}`")
        out.append("")
        out.append(f"{len(obs_par_code)} codes distincts" + (f", **{len(inconnus)} inconnus du moteur**" if rubrique == "S21.G00.81.001" else ""))
        out.append("")

        if rubrique == "S21.G00.81.001":
            out.append("| Code | Libellé officiel | Émis par EYWAI | Occurrences | Sociétés | Taux observés (%) |")
            out.append("|---|---|---|---:|---|---|")
            for code in sorted(obs_par_code):
                o = obs_par_code[code]
                statut = "oui" if code in connus else "**non**"
                taux = ", ".join(f"{t:g}" for t in o.taux_observes()) or "—"
                lib = libelle_cotisation(code) or "*hors nomenclature CT2026*"
                out.append(
                    f"| `{code}` | {lib} | {statut} | {o.occurrences} | "
                    f"{len(o.societes)}/{len(societes)} | {taux} |"
                )
        else:
            out.append("| Code | Occurrences | Sociétés |")
            out.append("|---|---:|---|")
            for code in sorted(obs_par_code):
                o = obs_par_code[code]
                out.append(f"| `{code}` | {o.occurrences} | {len(o.societes)}/{len(societes)} |")
        out.append("")

    # Contrôle de nos propres mappings contre le libellé officiel
    out.append("## Contrôle de nos mappings contre la nomenclature officielle")
    out.append("")
    out.append(
        "Pour chaque rubrique du moteur, le libellé officiel du code qu'elle "
        "produit. Une ligne dont le libellé ne parle pas de la même chose que "
        "le `coti_id` est une erreur de codage."
    )
    out.append("")
    out.append("| Rubrique moteur (`coti_id`) | Code émis | Libellé officiel du code |")
    out.append("|---|---|---|")
    for coti_id, code in sorted(COTI_ID_TO_DSN_CODE.items()):
        lib = libelle_cotisation(code) or "*inconnu de la nomenclature*"
        out.append(f"| `{coti_id}` | `{code.zfill(3)}` | {lib} |")
    out.append("")

    # Ce que le moteur sait produire sans jamais l'avoir vu déclaré
    vus = set(resultat["S21.G00.81.001"].keys())
    jamais_vus = sorted(connus - vus)
    if jamais_vus:
        out.append("## Codes que le moteur sait produire mais qu'aucune DSN n'utilise")
        out.append("")
        out.append(
            "Ils ne sont pas forcément faux : la situation ne s'est peut-être pas "
            "présentée sur la période. À vérifier avant de s'en servir."
        )
        out.append("")
        out.append(", ".join(f"`{c}`" for c in jamais_vus))
        out.append("")

    # Codes rares : présents chez une seule société ou un seul mois
    rares = [
        (code, o)
        for code, o in resultat["S21.G00.81.001"].items()
        if len(o.societes) == 1 or len(o.mois) <= 2
    ]
    if rares:
        out.append("## Codes rares — situations peu couvertes")
        out.append("")
        out.append(
            "Une seule société, ou deux mois au plus. Notre reconstitution y est "
            "la plus fragile : c'est là qu'un cas de gestion absent de la période "
            "(rupture, exonération ponctuelle) resterait invisible."
        )
        out.append("")
        out.append("| Code | Sociétés | Mois | Occurrences |")
        out.append("|---|---|---|---:|")
        for code, o in sorted(rares):
            out.append(
                f"| `{code}` | {', '.join(sorted(o.societes))} | "
                f"{len(o.mois)} | {o.occurrences} |"
            )
        out.append("")

    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sortie",
        default=str(ROOT / "data" / "_dsn_conformance" / "nomenclature-reconstituee.md"),
    )
    args = parser.parse_args()

    fichiers = sorted((ROOT / "data").glob("*/dsn/*.dsn"))
    if not fichiers:
        print("Aucune DSN trouvée sous data/*/dsn/", file=sys.stderr)
        return 1

    resultat = analyser(fichiers)
    texte = rapport(resultat, fichiers)

    sortie = pathlib.Path(args.sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(texte, encoding="utf-8")

    connus = codes_connus_du_moteur()
    cotis = resultat["S21.G00.81.001"]
    inconnus = sorted(c for c in cotis if c not in connus)
    print(f"{len(fichiers)} DSN analysées, {len(cotis)} codes de cotisation distincts.")
    print(f"Inconnus du moteur : {len(inconnus)} → {', '.join(inconnus) or 'aucun'}")
    print(f"Rapport : {sortie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

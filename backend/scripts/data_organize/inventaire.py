"""Inventaire et classification des données de paie éparpillées.

Parcourt les racines historiques (`Config/`, `Bulletins/`, `CARTOL/`, les `.dsn`
de la racine du dépôt), calcule l'empreinte de chaque fichier, en déduit sa
destination canonique sous `data/`, et signale doublons et versions divergentes.

N'écrit ni ne déplace rien : produit un plan JSON consommé par `migrer.py`.

    python -m scripts.data_organize.inventaire            # rapport lisible
    python -m scripts.data_organize.inventaire --json PLAN # écrit le plan
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from scripts.data_organize import convention as cv

RACINE_DEPOT = Path(__file__).resolve().parents[3]
RACINE_DATA = RACINE_DEPOT / "data"

#: Racines historiques à inventorier, relatives à la racine du dépôt.
RACINES_SOURCES = ("Config", "Bulletins", "CARTOL")

#: Fichiers système jamais migrés.
IGNORES = {".DS_Store", "Icon\r", "Thumbs.db", ".localized"}

_RE_DOSSIER_MOIS = re.compile(r"^(0[1-9]|1[0-2])$")
_RE_DOSSIER_BULLETINS_MD = re.compile(r"bulletins?_md[_-](20\d{2})-(\d{2})", re.IGNORECASE)


@dataclass
class Element:
    """Un fichier source et sa destination calculée."""

    source: Path  # relatif à la racine du dépôt
    taille: int
    empreinte: str
    societe: str | None = None
    rubrique: str | None = None
    periode: str | None = None
    cible: Path | None = None  # relatif à `data/`
    motif: str = ""

    @property
    def classe(self) -> bool:
        return self.cible is not None


@dataclass
class Plan:
    elements: list[Element] = field(default_factory=list)
    conflits: dict[str, list[Element]] = field(default_factory=dict)
    doublons: dict[str, list[Element]] = field(default_factory=dict)
    non_classes: list[Element] = field(default_factory=list)


def empreinte_fichier(chemin: Path, blocs: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with chemin.open("rb") as flux:
        while bloc := flux.read(blocs):
            digest.update(bloc)
    return digest.hexdigest()


def _societe_depuis_chemin(relatif: Path) -> str | None:
    """Cherche la société dans les segments du chemin, du plus proche au plus loin."""
    for segment in relatif.parts:
        if slug := cv.detecter_societe(segment):
            return slug
    return None


def _periode_depuis_dossiers(relatif: Path) -> str | None:
    """Mois encodé par les dossiers parents, du plus proche au plus lointain.

    `Bulletins/BULLETIN MBC 01 02 03 04 05 06/05/` encode le mois dans un segment
    à deux chiffres ; `bulletins_md_2026-05/` l'écrit en clair.
    """
    for segment in reversed(relatif.parts[:-1]):
        if m := _RE_DOSSIER_BULLETINS_MD.search(segment):
            return f"{m.group(1)}-{m.group(2)}"
        if _RE_DOSSIER_MOIS.match(segment):
            return f"{cv.ANNEE_PAR_DEFAUT}-{segment}"
        # Un dossier « BULLETIN MBC 01 02 03 04 05 06 » énumère les mois
        # disponibles, il n'en désigne aucun.
        if segment.count(" 0") >= 2:
            continue
        if periode := cv.detecter_periode_explicite(segment):
            return periode
    return None


def _periode_depuis_chemin(relatif: Path, nom: str) -> str | None:
    """Période d'un document, du signal le plus fiable au plus faible.

    1. Un mois écrit en toutes lettres dans le nom (`05-2026`, bloc DSN).
    2. Le dossier de rangement (`…/05/`, `bulletins_md_2026-05/`).
    3. Un numéro de semaine dans le nom — dernier recours, car une semaine à
       cheval sur deux mois trompe : la semaine 18 de 2026 a son jeudi en avril
       alors que le relevé sert la paie de mai.
    4. Une année seule.
    """
    return (
        cv.detecter_periode_explicite(nom)
        or _periode_depuis_dossiers(relatif)
        or cv.detecter_periode_semaine(nom)
        or cv.detecter_annee(nom)
    )


def _est_extrait_markdown(relatif: Path) -> bool:
    return relatif.suffix.lower() == ".md" and any(
        _RE_DOSSIER_BULLETINS_MD.search(p) for p in relatif.parts
    )


def classer(relatif: Path) -> Element | None:
    """Calcule la destination canonique d'un fichier source."""
    absolu = RACINE_DEPOT / relatif
    element = Element(
        source=relatif,
        taille=absolu.stat().st_size,
        empreinte=empreinte_fichier(absolu),
    )

    nom = relatif.name
    parent = relatif.parent.name

    element.societe = _societe_depuis_chemin(relatif)
    element.rubrique = cv.detecter_rubrique(nom, parent)
    element.periode = _periode_depuis_chemin(relatif, nom)

    # Les extraits Cegid par salarié sont des bulletins, quel que soit leur nom
    # (un fichier nommé d'après un matricule ne porte aucun indice exploitable).
    if _est_extrait_markdown(relatif):
        element.rubrique = cv.BULLETINS

    # Sous `Bulletins/`, un document non identifié autrement est le bulletin du
    # mois : `01-26 CARTOL.pdf`, `05-2026 COMITECH.pdf`.
    if element.rubrique is None and relatif.parts[0] == "Bulletins":
        element.rubrique = cv.BULLETINS

    if not element.societe:
        element.motif = "société indéterminée"
        return element
    if not element.rubrique:
        element.motif = "rubrique indéterminée"
        return element

    nom_cible = cv.nom_canonique(element.rubrique, element.periode, nom)
    destination = cv.Destination(
        societe=element.societe,
        rubrique=element.rubrique,
        periode=element.periode,
        nom=nom_cible,
    )
    cible = destination.chemin_relatif()

    # Les extraits markdown vivent dans un sous-dossier `md/` pour ne pas noyer
    # le PDF du bulletin sous 150 fichiers.
    if _est_extrait_markdown(relatif):
        cible = cible.parent / "md" / relatif.name

    element.cible = cible
    return element


def construire_plan(racines: tuple[str, ...] = RACINES_SOURCES) -> Plan:
    plan = Plan()

    chemins: list[Path] = []
    for racine in racines:
        base = RACINE_DEPOT / racine
        if not base.exists():
            continue
        for chemin in base.rglob("*"):
            if chemin.is_file() and chemin.name not in IGNORES:
                chemins.append(chemin.relative_to(RACINE_DEPOT))

    # Les DSN abandonnées à la racine du dépôt.
    for chemin in RACINE_DEPOT.glob("*.dsn"):
        chemins.append(chemin.relative_to(RACINE_DEPOT))

    for relatif in sorted(chemins):
        element = classer(relatif)
        if element is None:
            continue
        plan.elements.append(element)
        if not element.classe:
            plan.non_classes.append(element)

    par_empreinte: dict[str, list[Element]] = defaultdict(list)
    par_cible: dict[str, list[Element]] = defaultdict(list)
    for element in plan.elements:
        if element.classe:
            par_empreinte[element.empreinte].append(element)
            par_cible[str(element.cible)].append(element)

    plan.doublons = {h: els for h, els in par_empreinte.items() if len(els) > 1}
    plan.conflits = {
        cible: els
        for cible, els in par_cible.items()
        if len({e.empreinte for e in els}) > 1
    }
    return plan


def _serialiser(plan: Plan) -> dict:
    return {
        "elements": [
            {
                "source": str(e.source),
                "cible": str(e.cible) if e.cible else None,
                "societe": e.societe,
                "rubrique": e.rubrique,
                "periode": e.periode,
                "empreinte": e.empreinte,
                "taille": e.taille,
                "motif": e.motif,
            }
            for e in plan.elements
        ],
        "conflits": {c: [str(e.source) for e in els] for c, els in plan.conflits.items()},
        "doublons": {h: [str(e.source) for e in els] for h, els in plan.doublons.items()},
    }


def afficher_rapport(plan: Plan) -> None:
    classes = [e for e in plan.elements if e.classe]
    print(f"Fichiers inventoriés : {len(plan.elements)}")
    print(f"  classés            : {len(classes)}")
    print(f"  non classés        : {len(plan.non_classes)}")

    par_societe: dict[str, int] = defaultdict(int)
    par_rubrique: dict[str, int] = defaultdict(int)
    for element in classes:
        par_societe[element.societe or "?"] += 1
        par_rubrique[element.rubrique or "?"] += 1

    print("\nPar société :")
    for societe, nombre in sorted(par_societe.items(), key=lambda kv: -kv[1]):
        print(f"  {societe:<12} {nombre:>4}")

    print("\nPar rubrique :")
    for rubrique, nombre in sorted(par_rubrique.items(), key=lambda kv: -kv[1]):
        print(f"  {rubrique:<12} {nombre:>4}")

    if plan.doublons:
        print(f"\nDoublons exacts (même contenu) : {len(plan.doublons)} groupe(s)")
        for elements in list(plan.doublons.values())[:10]:
            print(f"  - {elements[0].cible}")
            for element in elements:
                print(f"      {element.source}")

    if plan.conflits:
        print(f"\nVersions divergentes (même cible, contenu différent) : {len(plan.conflits)}")
        for cible, elements in list(plan.conflits.items())[:15]:
            print(f"  - {cible}")
            for element in elements:
                horodatage = (RACINE_DEPOT / element.source).stat().st_mtime
                import datetime as dt

                date = dt.datetime.fromtimestamp(horodatage).strftime("%Y-%m-%d")
                print(f"      {date}  {element.taille:>9}  {element.source}")

    if plan.non_classes:
        print(f"\nNon classés : {len(plan.non_classes)}")
        for element in plan.non_classes[:25]:
            print(f"  [{element.motif}] {element.source}")


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--json", type=Path, help="écrit le plan au format JSON")
    arguments = analyseur.parse_args(argv)

    plan = construire_plan()
    afficher_rapport(plan)

    if arguments.json:
        arguments.json.write_text(
            json.dumps(_serialiser(plan), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nPlan écrit dans {arguments.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

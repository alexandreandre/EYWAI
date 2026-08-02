"""Migration des données de paie vers la racine `data/`.

Déplace chaque fichier vers sa destination canonique, archive (sans jamais
supprimer) les doublons et les versions perdantes, puis pose des liens
symboliques aux anciens emplacements pour qu'aucun script existant ne casse.

Toute la migration est journalisée dans `data/_manifeste.json` et annulable par
`rollback.py`.

    python -m scripts.data_organize.migrer              # simulation
    python -m scripts.data_organize.migrer --appliquer  # exécution
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from scripts.data_organize import convention as cv
from scripts.data_organize.inventaire import RACINE_DATA, RACINE_DEPOT, Element, construire_plan

MANIFESTE = RACINE_DATA / "_manifeste.json"

#: Sous-dossiers d'archive, par motif de mise à l'écart.
ARCH_DOUBLONS = Path(cv.ARCHIVE) / "doublons"
ARCH_VERSIONS = Path(cv.ARCHIVE) / "versions-anterieures"
ARCH_NON_CLASSES = Path(cv.ARCHIVE) / "non-classes"

#: Actions possibles, journalisées dans le manifeste.
RANGE = "range"
ARCHIVE_DOUBLON = "archive-doublon"
ARCHIVE_VERSION = "archive-version"
ARCHIVE_NON_CLASSE = "archive-non-classe"


@dataclass
class Mouvement:
    """Un déplacement à effectuer, ou effectué."""

    source: Path  # relatif à la racine du dépôt
    cible: Path  # relatif à `data/`
    action: str
    empreinte: str
    raison: str = ""

    def en_dict(self) -> dict:
        return {
            "source": str(self.source),
            "cible": str(self.cible),
            "action": self.action,
            "empreinte": self.empreinte,
            "raison": self.raison,
        }


def _aplatir(source: Path) -> str:
    """`Config/MBC/Calendrier/x.xlsx` -> `config-mbc-calendrier--x.xlsx`.

    Un fichier archivé garde ainsi la trace de son emplacement d'origine, sans
    recréer toute l'arborescence sous `_archive/`.
    """
    prefixe = cv.slugifier(str(source.parent)) or "racine"
    return f"{prefixe}--{source.name}"


def _mtime(relatif: Path) -> float:
    return (RACINE_DEPOT / relatif).stat().st_mtime


def _date_courte(relatif: Path) -> str:
    return dt.datetime.fromtimestamp(_mtime(relatif)).strftime("%Y-%m-%d")


def construire_mouvements() -> tuple[list[Mouvement], dict]:
    """Traduit le plan d'inventaire en liste de déplacements sans ambiguïté.

    Règles d'arbitrage :

    - plusieurs fichiers pour une même cible et un même contenu : le premier
      rangé gagne, les autres sont archivés comme doublons ;
    - plusieurs fichiers pour une même cible et des contenus différents : le
      plus récemment modifié gagne, les autres sont archivés comme versions
      antérieures, suffixés de leur date ;
    - fichier non classé : archivé tel quel, jamais supprimé.
    """
    plan = construire_plan()
    mouvements: list[Mouvement] = []

    par_cible: dict[str, list[Element]] = defaultdict(list)
    for element in plan.elements:
        if element.classe:
            par_cible[str(element.cible)].append(element)

    for cible, elements in sorted(par_cible.items()):
        # Le plus récent d'abord : il remporte le nom canonique.
        elements.sort(key=lambda e: _mtime(e.source), reverse=True)
        gagnant = elements[0]
        mouvements.append(
            Mouvement(
                source=gagnant.source,
                cible=Path(cible),
                action=RANGE,
                empreinte=gagnant.empreinte,
            )
        )
        for perdant in elements[1:]:
            if perdant.empreinte == gagnant.empreinte:
                mouvements.append(
                    Mouvement(
                        source=perdant.source,
                        cible=ARCH_DOUBLONS / _aplatir(perdant.source),
                        action=ARCHIVE_DOUBLON,
                        empreinte=perdant.empreinte,
                        raison=f"contenu identique à {cible}",
                    )
                )
            else:
                nom = _aplatir(perdant.source)
                radical, point, extension = nom.rpartition(".")
                horodate = f"{radical}--{_date_courte(perdant.source)}{point}{extension}"
                mouvements.append(
                    Mouvement(
                        source=perdant.source,
                        cible=ARCH_VERSIONS / horodate,
                        action=ARCHIVE_VERSION,
                        empreinte=perdant.empreinte,
                        raison=f"version antérieure de {cible}",
                    )
                )

    for element in plan.non_classes:
        mouvements.append(
            Mouvement(
                source=element.source,
                cible=ARCH_NON_CLASSES / _aplatir(element.source),
                action=ARCHIVE_NON_CLASSE,
                empreinte=element.empreinte,
                raison=element.motif,
            )
        )

    resume = {
        "total": len(mouvements),
        "ranges": sum(1 for m in mouvements if m.action == RANGE),
        "doublons": sum(1 for m in mouvements if m.action == ARCHIVE_DOUBLON),
        "versions": sum(1 for m in mouvements if m.action == ARCHIVE_VERSION),
        "non_classes": sum(1 for m in mouvements if m.action == ARCHIVE_NON_CLASSE),
    }
    return mouvements, resume


def _lien_relatif(depuis: Path, vers: Path) -> Path:
    """Cible d'un symlink posé en `depuis`, exprimée relativement à son dossier."""
    return Path(os.path.relpath(vers, start=depuis.parent))


def appliquer(mouvements: list[Mouvement], compat: bool = True) -> dict:
    """Exécute les déplacements et pose les liens de compatibilité.

    Le lien symbolique laissé à l'ancien emplacement garantit que les scripts
    de backtest et le code applicatif continuent de résoudre leurs chemins en
    dur, sans qu'aucun fichier source n'ait à être modifié.
    """
    RACINE_DATA.mkdir(parents=True, exist_ok=True)
    effectues: list[Mouvement] = []

    for mouvement in mouvements:
        source = RACINE_DEPOT / mouvement.source
        cible = RACINE_DATA / mouvement.cible

        if not source.exists() or source.is_symlink():
            continue

        cible.parent.mkdir(parents=True, exist_ok=True)
        if cible.exists():
            raise RuntimeError(f"cible déjà occupée, migration interrompue : {cible}")

        source.rename(cible)
        if compat:
            source.symlink_to(_lien_relatif(source, cible))
        effectues.append(mouvement)

    manifeste = {
        "version": 1,
        "genere_le": dt.datetime.now().isoformat(timespec="seconds"),
        "racine_data": str(RACINE_DATA.relative_to(RACINE_DEPOT)),
        "liens_compatibilite": compat,
        "mouvements": [m.en_dict() for m in effectues],
    }
    MANIFESTE.write_text(
        json.dumps(manifeste, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"effectues": len(effectues), "manifeste": str(MANIFESTE)}


def afficher(mouvements: list[Mouvement], resume: dict, limite: int = 20) -> None:
    print("Mouvements prévus")
    print(f"  rangés               : {resume['ranges']:>5}")
    print(f"  archivés (doublon)   : {resume['doublons']:>5}")
    print(f"  archivés (version)   : {resume['versions']:>5}")
    print(f"  archivés (non classé): {resume['non_classes']:>5}")
    print(f"  TOTAL                : {resume['total']:>5}")

    print(f"\nExtrait ({limite} premiers rangements) :")
    montres = 0
    for mouvement in mouvements:
        if mouvement.action != RANGE:
            continue
        print(f"  {mouvement.source}")
        print(f"    -> data/{mouvement.cible}")
        montres += 1
        if montres >= limite:
            break

    ecartes = [m for m in mouvements if m.action == ARCHIVE_VERSION]
    if ecartes:
        print(f"\nVersions écartées ({len(ecartes)}) — conservées dans data/_archive/ :")
        for mouvement in ecartes:
            print(f"  {mouvement.source}")
            print(f"    ({mouvement.raison})")


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument(
        "--appliquer", action="store_true", help="exécute réellement les déplacements"
    )
    analyseur.add_argument(
        "--sans-compat",
        action="store_true",
        help="ne pose pas les liens symboliques aux anciens emplacements",
    )
    arguments = analyseur.parse_args(argv)

    mouvements, resume = construire_mouvements()
    afficher(mouvements, resume)

    if not arguments.appliquer:
        print("\nSimulation. Rien n'a été déplacé. Ajouter --appliquer pour exécuter.")
        return 0

    rapport = appliquer(mouvements, compat=not arguments.sans_compat)
    print(f"\n{rapport['effectues']} fichiers déplacés.")
    print(f"Manifeste : {rapport['manifeste']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

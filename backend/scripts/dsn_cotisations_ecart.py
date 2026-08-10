"""Mesure la conformité des blocs cotisation de notre DSN (78 / 81).

Le comparateur général (`domain/conformance.py`) compare rubrique par rubrique
et perd l'appariement : il voit bien la liste des codes et la liste des
montants, mais pas quel montant va avec quel code. Pour les cotisations, c'est
justement l'appariement qui compte. Ce script recompose donc chaque ligne
`(base, code) → assiette, montant, taux` et la confronte à la DSN du cabinet.

Il sépare surtout deux choses qu'il ne faut pas mélanger :

- **l'écart de traduction**, dont nous sommes responsables : le bon code, sur
  la bonne base, au bon taux ;
- **l'écart de paie**, qui vient d'un brut différent du leur et fait diverger
  tous les montants d'un même salarié en proportion.

Un salarié dont le brut diverge est donc mesuré à part : sa DSN ne peut pas
être juste, et le compter avec les autres masquerait l'état réel de la
traduction.

    venv/bin/python -m scripts.dsn_cotisations_ecart
    venv/bin/python -m scripts.dsn_cotisations_ecart --societe colorplast --detail
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys
from typing import Any, Dict, List, Optional, Tuple

RACINE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "backend"))

from app.modules.dsn_export.application.builder import (  # noqa: E402
    build_parsed_dsn_from_payroll,
)
from app.modules.dsn_export.domain.conformance import lire_rubriques  # noqa: E402
from app.modules.dsn_export.domain.nomenclature_cotisation import (  # noqa: E402
    libelle_cotisation,
)
from app.modules.dsn_export.domain.settings import depuis_dict  # noqa: E402
from app.modules.dsn_export.domain.writer import encode_dsn_bytes  # noqa: E402

INSTANTANES = RACINE / "data" / "_dsn_conformance"

# Sous ce seuil, deux montants sont tenus pour égaux.
TOLERANCE = 0.005
# Un brut qui diverge de plus d'un centime rend la comparaison des cotisations
# sans objet pour ce salarié.
TOLERANCE_BRUT = 0.01


Ligne = Dict[str, str]


def lignes_cotisation(contenu: bytes) -> Dict[str, Dict[Tuple[str, str], Ligne]]:
    """{nir13: {(base, code): rubriques de la ligne}}."""
    par_individu: Dict[str, Dict[Tuple[str, str], Ligne]] = {}
    nir: Optional[str] = None
    base = ""
    cle: Optional[Tuple[str, str]] = None
    for rubrique, valeur in lire_rubriques(contenu):
        if rubrique == "S21.G00.30.001":
            nir = "".join(c for c in valeur if c.isdigit())[:13]
            par_individu.setdefault(nir, {})
            base, cle = "", None
        elif rubrique == "S21.G00.78.001":
            base = valeur.zfill(2)
            cle = None
        elif rubrique == "S21.G00.81.001" and nir is not None:
            cle = (base, valeur.zfill(3))
            # Deux lignes de même code et même base (prévoyance multi-affiliation)
            # se cumulent : c'est le total qui se compare.
            par_individu[nir].setdefault(cle, {"004": "0"})
        elif rubrique.startswith("S21.G00.81.") and nir is not None and cle is not None:
            champ = rubrique[-3:]
            courante = par_individu[nir][cle]
            if champ == "004":
                courante["004"] = f"{float(courante.get('004') or 0) + float(valeur):.2f}"
            else:
                courante.setdefault(champ, valeur)
    return par_individu


def bruts(contenu: bytes) -> Dict[str, float]:
    """Assiette brute déplafonnée (base 03) par individu : le pivot de la paie."""
    resultat: Dict[str, float] = {}
    nir: Optional[str] = None
    base = ""
    for rubrique, valeur in lire_rubriques(contenu):
        if rubrique == "S21.G00.30.001":
            nir = "".join(c for c in valeur if c.isdigit())[:13]
        elif rubrique == "S21.G00.78.001":
            base = valeur.zfill(2)
        elif rubrique == "S21.G00.78.004" and base == "03" and nir:
            resultat[nir] = float(valeur)
    return resultat


def _nombre(ligne: Ligne, champ: str) -> float:
    try:
        return float(ligne.get(champ) or 0)
    except (TypeError, ValueError):
        return 0.0


class Compte:
    def __init__(self) -> None:
        self.codes_manquants: collections.Counter = collections.Counter()
        self.codes_en_trop: collections.Counter = collections.Counter()
        self.montants: collections.Counter = collections.Counter()
        self.taux: collections.Counter = collections.Counter()
        self.individus_conformes = 0
        self.individus_compares = 0


def comparer_individu(notre: Dict[Tuple[str, str], Ligne], reference: Dict[Tuple[str, str], Ligne], compte: Compte) -> bool:
    conforme = True
    for cle in set(reference) - set(notre):
        compte.codes_manquants[cle] += 1
        conforme = False
    for cle in set(notre) - set(reference):
        compte.codes_en_trop[cle] += 1
        conforme = False
    for cle in set(notre) & set(reference):
        a, b = notre[cle], reference[cle]
        if abs(_nombre(a, "004") - _nombre(b, "004")) > TOLERANCE:
            compte.montants[cle] += 1
            conforme = False
        elif abs(_nombre(a, "007") - _nombre(b, "007")) > TOLERANCE:
            compte.taux[cle] += 1
            conforme = False
    return conforme


def instantanes(filtre: Optional[str]) -> List[Tuple[str, str, pathlib.Path]]:
    trouves = []
    for entree in sorted(INSTANTANES.glob("*/*/input.json")):
        repertoire = entree.parent
        societe = repertoire.parent.name
        if filtre and societe != filtre:
            continue
        if (repertoire / "reference.dsn").exists():
            trouves.append((societe, repertoire.name, repertoire))
    return trouves


def traiter(repertoire: pathlib.Path) -> Tuple[bytes, bytes, List[str]]:
    donnees: Dict[str, Any] = json.loads((repertoire / "input.json").read_text())
    fichier, avertissements = build_parsed_dsn_from_payroll(
        donnees["company"],
        donnees["employees_data"],
        donnees["periode"],
        file_name="conformite.dsn",
        settings=depuis_dict(donnees.get("dsn_settings")),
    )
    return encode_dsn_bytes(fichier), (repertoire / "reference.dsn").read_bytes(), avertissements


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--societe", help="ne traiter qu'une société")
    parser.add_argument("--detail", action="store_true", help="détailler les écarts par code")
    args = parser.parse_args()

    lots = instantanes(args.societe)
    if not lots:
        print("Aucun instantané. Lancer scripts/dsn_conformance_snapshot.py", file=sys.stderr)
        return 1

    global_compte = Compte()
    total_paie = 0
    for societe, periode, repertoire in lots:
        notre_contenu, contenu_reference, _ = traiter(repertoire)
        notre = lignes_cotisation(notre_contenu)
        reference = lignes_cotisation(contenu_reference)
        notre_brut, brut_reference = bruts(notre_contenu), bruts(contenu_reference)

        compte = Compte()
        ecart_paie = 0
        for nir in sorted(set(notre) & set(reference)):
            if abs(notre_brut.get(nir, 0) - brut_reference.get(nir, 0)) > TOLERANCE_BRUT:
                ecart_paie += 1
                continue
            compte.individus_compares += 1
            if comparer_individu(notre[nir], reference[nir], compte):
                compte.individus_conformes += 1

        total_paie += ecart_paie
        for source, cible in (
            (compte.codes_manquants, global_compte.codes_manquants),
            (compte.codes_en_trop, global_compte.codes_en_trop),
            (compte.montants, global_compte.montants),
            (compte.taux, global_compte.taux),
        ):
            cible.update(source)
        global_compte.individus_compares += compte.individus_compares
        global_compte.individus_conformes += compte.individus_conformes

        part = (
            f"{compte.individus_conformes}/{compte.individus_compares}"
            if compte.individus_compares
            else "—"
        )
        print(
            f"{societe:11s} {periode}  cotisations conformes : {part:>9s}"
            f"   (+{ecart_paie} salariés écartés, brut divergent)"
        )

    print()
    part = (
        f"{global_compte.individus_conformes}/{global_compte.individus_compares}"
        if global_compte.individus_compares
        else "—"
    )
    print(f"Total : {part} salariés dont les cotisations sont conformes au centime.")
    print(f"{total_paie} salariés écartés : leur brut diffère de celui du cabinet.")

    if args.detail:
        for titre, compteur in (
            ("Codes attendus et absents", global_compte.codes_manquants),
            ("Codes produits en trop", global_compte.codes_en_trop),
            ("Montants divergents", global_compte.montants),
            ("Taux divergents", global_compte.taux),
        ):
            if not compteur:
                continue
            print(f"\n{titre} :")
            for (base, code), nombre in compteur.most_common(15):
                print(f"  base {base} code {code}  {nombre:4d}  {libelle_cotisation(code)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

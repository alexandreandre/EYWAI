"""Grilles mutuelle réelles, lues dans les bulletins du cabinet.

Contexte
--------
EYWAI porte la cotisation mutuelle **en entier** à la charge du salarié : les
lignes issues de l'import DSN valent 59,27 €, 119,75 €, 116,06 €… avec une part
patronale à zéro. Ces montants sont en réalité des *totaux* — le bulletin Cegid
les répartit en deux :

    EMU1 MUTUELLE ISOLE   29.64  1.0000  29.64  29.63
                          base   taux    salarial  patronal

29,64 + 29,63 = 59,27. Le rapprochement est arithmétique, pas approximatif.

Ce script ne touche à aucune base : il lit les PDF de bulletins et produit, par
société, la formule de chaque salarié avec les deux parts. Le fichier de sortie
est nominatif — il va dans `data/`, jamais dans le code.

Usage
-----
    python scripts/extraire_mutuelles_bulletins.py                  # cartol + lewis, juillet 2026
    python scripts/extraire_mutuelles_bulletins.py --societe cartol --periode 2026-07
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
DATA = RACINE / "data"

# « CODE LIBELLÉ   base   taux   montant_salarial   montant_patronal »
LIGNE_MUTUELLE = re.compile(
    r"^\s*(EMU\w*)\s+(.+?)\s{2,}"
    r"(-?[\d ]+[.,]\d{2})\s+"
    r"(-?[\d ]+[.,]\d{4})\s+"
    r"(-?[\d ]+[.,]\d{2})\s+"
    r"(-?[\d ]+[.,]\d{2})"
)
MATRICULE = re.compile(r"Matricule\s*:\s*(\S+)")
NOM = re.compile(r"^\s{2,}(M(?:R|ME|LLE)?\s+.+?)\s*$", re.MULTILINE)


def _nombre(txt: str) -> float:
    return float(txt.replace(" ", "").replace(",", "."))


def pdf_en_texte(pdf: Path) -> str:
    """Cegid pose ses bulletins en colonnes : sans -layout, les montants se mélangent."""
    sortie = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True, check=True,
    )
    return sortie.stdout.decode("utf-8", errors="replace")


def decouper_bulletins(texte: str):
    """Un bulletin = de « Matricule : X » au « Matricule : » suivant.

    Le nom du salarié figure AU-DESSUS de sa ligne « Matricule : » : on le
    cherche dans la fenêtre qui précède, jamais dans le corps du bulletin —
    sinon on récupère le nom du salarié suivant.
    """
    positions = [(m.start(), m.group(1)) for m in MATRICULE.finditer(texte)]
    for i, (debut, matricule) in enumerate(positions):
        fin = positions[i + 1][0] if i + 1 < len(positions) else len(texte)
        entete_debut = positions[i - 1][0] if i else 0
        yield matricule, texte[entete_debut:debut], texte[debut:fin]


def extraire(pdf: Path) -> tuple[list[dict], int]:
    texte = pdf_en_texte(pdf)
    lignes: dict[str, dict] = {}
    for matricule, entete, bloc in decouper_bulletins(texte):
        if matricule in lignes:
            continue  # page 2 du même bulletin
        noms = NOM.findall(entete)
        for brute in bloc.splitlines():
            m = LIGNE_MUTUELLE.match(brute)
            if not m:
                continue
            code, libelle, _base, _taux, salarial, patronal = m.groups()
            lignes[matricule] = {
                "matricule": matricule,
                "nom": noms[-1].strip() if noms else "",
                "code": code,
                "libelle": " ".join(libelle.split()),
                "part_salariale": _nombre(salarial),
                "part_patronale": _nombre(patronal),
                "total": round(_nombre(salarial) + _nombre(patronal), 2),
            }
            break
    return list(lignes.values()), len(set(MATRICULE.findall(texte)))


def traiter(societe: str, periode: str) -> int:
    dossier = DATA / societe / "bulletins" / periode
    pdfs = sorted(dossier.glob("*.pdf"))
    if not pdfs:
        print(f"  aucun bulletin dans {dossier}")
        return 1

    lignes: list[dict] = []
    bulletins = 0
    for pdf in pdfs:
        trouvees, total = extraire(pdf)
        lignes.extend(trouvees)
        bulletins += total

    destination = DATA / societe / "referentiel" / f"mutuelles-{periode}.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["matricule", "nom", "code", "libelle",
                        "part_salariale", "part_patronale", "total"],
            delimiter=";",
        )
        w.writeheader()
        w.writerows(sorted(lignes, key=lambda l: l["matricule"]))

    grilles: dict[tuple, int] = {}
    for l in lignes:
        cle = (l["code"], l["libelle"], l["part_salariale"],
               l["part_patronale"], l["total"])
        grilles[cle] = grilles.get(cle, 0) + 1

    print(f"\n=== {societe.upper()} {periode} ===")
    print(f"  bulletins lus : {bulletins} — avec ligne mutuelle : {len(lignes)}")
    for (code, libelle, sal, pat, total), n in sorted(
        grilles.items(), key=lambda kv: -kv[1]
    ):
        print(f"  {code:5} {libelle:30} {sal:>7.2f} + {pat:>6.2f} = {total:>7.2f}  ×{n}")
    print(f"  → {destination.relative_to(RACINE)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--societe", action="append",
                        help="société à traiter (défaut : cartol et lewis)")
    parser.add_argument("--periode", default="2026-07", help="AAAA-MM")
    args = parser.parse_args()

    societes = args.societe or ["cartol", "lewis"]
    code = 0
    for societe in societes:
        code |= traiter(societe, args.periode)
    return code


if __name__ == "__main__":
    sys.exit(main())

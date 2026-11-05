"""Construit `app/modules/pcs_ese/data/pcs_ese_2017.json`.

Deux sources officielles, téléchargées par curl :
- la table DSN « PCSESE » P26V01 de net-entreprises (430 codes, datée du 25/09/2025), qui fait
  foi pour la liste et les libellés ;
- les 429 pages Insee de la PCS-ESE 2017
  (https://www.insee.fr/fr/metadonnees/pcsese2017/rubriqueRegroupee/<code>), pour les
  professions typiques, assimilées et exclues.

Usage (depuis backend/) :
    .venv/bin/python -I scripts/pcs_ese/construire_referentiel.py \
        --pages ../data/_sources/insee/pcs-ese-2017-pages-2026-11-05 \
        --table ../data/_sources/net-entreprises/NEODESP26-PCSESE-P26V01.csv \
        --telecharge-le 2026-11-05
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

SORTIE = Path(__file__).resolve().parents[2] / "app" / "modules" / "pcs_ese" / "data" / "pcs_ese_2017.json"
SECTIONS = {
    "Professions les plus typiques": "typiques",
    "Professions assimilées": "assimilees",
    "Professions exclues": "exclues",
}
CODE = re.compile(r"\d{3}[a-z]")


def lire_table(chemin: Path) -> list[tuple[str, str]]:
    lignes = chemin.read_bytes().decode("latin-1").splitlines()
    codes = []
    for ligne in lignes[1:]:
        if ";" in ligne:
            code, libelle = ligne.split(";", 1)
            codes.append((code.strip(), libelle.strip()))
    return codes


def lire_page(chemin: Path, code: str) -> dict:
    texte = chemin.read_text(encoding="utf-8", errors="replace")
    texte = re.sub(r"<script.*?</script>|<style.*?</style>", "", texte, flags=re.S)
    brut = html.unescape(re.sub(r"<[^>]+>", "\n", texte))
    lignes = [ligne.strip() for ligne in brut.split("\n") if ligne.strip()]
    titre = f"Rubrique {code} :"
    debut = next(i for i, ligne in enumerate(lignes) if ligne.startswith(titre))
    page = {"typiques": [], "assimilees": [], "exclues": [], "mise_a_jour": None}
    courante = None
    for i in range(debut, len(lignes)):
        ligne = lignes[i]
        if ligne.startswith("Nos sites partenaires"):
            break
        if ligne.startswith("Dernière mise à jour"):
            date = re.search(r"\d{2}/\d{2}/\d{4}", " ".join(lignes[i : i + 2]))
            page["mise_a_jour"] = page["mise_a_jour"] or (date.group(0) if date else None)
            continue
        if re.fullmatch(r":\s*\d{2}/\d{2}/\d{4}", ligne):
            continue
        if ligne in SECTIONS:
            courante = SECTIONS[ligne]
            continue
        if courante == "exclues":
            voir = re.search(r"\(voir ([^)]*)\)\s*$", ligne)
            page["exclues"].append(
                {
                    "libelle": ligne[: voir.start()].strip() if voir else ligne,
                    "voir": CODE.findall(voir.group(1)) if voir else [],
                }
            )
        elif courante:
            page[courante].append(ligne)
    return page


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--pages", type=Path, required=True)
    args.add_argument("--table", type=Path, required=True)
    args.add_argument("--telecharge-le", required=True)
    opts = args.parse_args()

    rubriques = []
    for code, libelle in lire_table(opts.table):
        public = libelle.endswith("*")
        entree = {"code": code, "libelle": libelle.rstrip("*").strip(), "public": public}
        if code == "9999":
            entree.update(typiques=[], assimilees=[], exclues=[], mise_a_jour=None)
        else:
            entree.update(lire_page(opts.pages / f"{code}.html", code))
        rubriques.append(entree)

    sortie = {
        "sources": {
            "table": "https://portail.net-entreprises.fr/nmcl/telechargeFichierCsv/NEODESP26-PCSESE-P26V01.csv",
            "table_date": "25/09/2025",
            "pages": "https://www.insee.fr/fr/metadonnees/pcsese2017/rubriqueRegroupee/<code>",
            "telecharge_le": opts.telecharge_le,
        },
        "rubriques": rubriques,
    }
    SORTIE.write_text(json.dumps(sortie, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(rubriques)} codes écrits dans {SORTIE}")


if __name__ == "__main__":
    main()

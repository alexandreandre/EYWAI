"""Dérive le paramétrage prévoyance/santé (blocs 15 et 70) des DSN du cabinet.

Pour chaque société : la liste des contrats du bloc S21.G00.15, puis, salarié
par salarié (apparié par NIR aux jeux input.json), les blocs S21.G00.70 émis.
Objectif : vérifier si la règle « le statut cadre / non-cadre détermine les
affiliations » tient — c'est elle qui permettrait d'émettre le bloc 70 sans
saisie individuelle.

Lecture seule. Sortie : un rapport par société, et --json pour la config prête
à coller dans settings.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
FIXTURES = RACINE / "data" / "_dsn_conformance"


def lire_lignes(chemin: Path):
    for ligne in chemin.read_text(encoding="latin-1").splitlines():
        if "," not in ligne:
            continue
        rubrique, _, valeur = ligne.partition(",")
        yield rubrique, valeur.strip().strip("'")


def analyser(societe: str):
    dossier = next(iter(sorted((FIXTURES / societe).glob("2026-*"))), None)
    if not dossier or not (dossier / "reference.dsn").exists():
        return None

    contrats: list[dict] = []
    individus: list[dict] = []
    courant: dict | None = None
    affiliation: dict | None = None

    for rubrique, valeur in lire_lignes(dossier / "reference.dsn"):
        if rubrique == "S21.G00.15.001":
            contrats.append({"reference": valeur})
        elif rubrique.startswith("S21.G00.15.") and contrats:
            cle = {"002": "organisme", "003": "delegataire", "004": "nature", "005": "ordre"}
            suffixe = rubrique.rsplit(".", 1)[-1]
            if suffixe in cle:
                contrats[-1][cle[suffixe]] = valeur
        elif rubrique == "S21.G00.30.001":
            courant = {"nir": valeur, "statut": "", "affiliations": []}
            individus.append(courant)
        elif rubrique == "S21.G00.40.002" and courant is not None:
            courant["statut"] = courant["statut"] or valeur
        elif rubrique == "S21.G00.70.004" and courant is not None:
            affiliation = {"option": valeur}
            courant["affiliations"].append(affiliation)
        elif rubrique in ("S21.G00.70.005", "S21.G00.70.012", "S21.G00.70.013") and affiliation is not None:
            cle = {"005": "population", "012": "id_affiliation", "013": "id_contrat"}
            affiliation[cle[rubrique.rsplit(".", 1)[-1]]] = valeur

    # Statut réel depuis input.json (le 40.002 du cabinet est le conventionnel).
    entree = json.loads((dossier / "input.json").read_text())
    cadre_par_nir: dict[str, bool] = {}
    for ligne in entree["employees_data"]:
        employe = ligne.get("employee") or ligne
        nir = str(employe.get("nir") or employe.get("social_security_number") or "")
        nir = nir.replace(" ", "")[:13]
        statut = str(employe.get("statut") or employe.get("statut_salarie") or "").lower()
        cadre_par_nir[nir] = employe.get("is_cadre") is True or "cadre" in statut

    par_profil: dict[tuple, list] = defaultdict(list)
    for individu in individus:
        signature = tuple(
            sorted(
                (a.get("option", ""), a.get("population", ""), a.get("id_contrat", ""), a.get("id_affiliation", ""))
                for a in individu["affiliations"]
            )
        )
        cadre = cadre_par_nir.get(individu["nir"])
        libelle = {True: "cadre", False: "non-cadre", None: "inconnu"}[cadre]
        par_profil[(libelle, signature)].append(individu["nir"])

    return {"societe": societe, "contrats": contrats, "profils": par_profil, "nb": len(individus)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--societe")
    parser.add_argument("--json", action="store_true", help="config bloc 15 en JSON")
    parser.add_argument(
        "--ecrire",
        action="store_true",
        help="écrit organismes_complementaires dans le settings.json de chaque société",
    )
    args = parser.parse_args()

    societes = [args.societe] if args.societe else ["cartol", "colorplast", "comitech", "lewis", "mbc"]
    for societe in societes:
        resultat = analyser(societe)
        if not resultat:
            continue
        print(f"\n{'=' * 66}\n{societe} — {resultat['nb']} salariés, {len(resultat['contrats'])} contrats au bloc 15")
        if args.json:
            print(json.dumps(resultat["contrats"], indent=1, ensure_ascii=False))
        for (statut, signature), nirs in sorted(resultat["profils"].items()):
            blocs = " | ".join(
                f"opt={o or '—'} pop={p or '—'} ctr={c or '—'} aff={a or '—'}"
                for o, p, c, a in signature
            ) or "aucune affiliation"
            print(f"  {statut:9} ×{len(nirs):<3} {blocs}")

        if args.ecrire:
            chemin = FIXTURES / societe / "settings.json"
            if not chemin.exists():
                print("  (pas de settings.json, ignoré)")
                continue
            donnees = json.loads(chemin.read_text())
            donnees["organismes_complementaires"] = resultat["contrats"]
            chemin.write_text(
                json.dumps(donnees, indent=1, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"  -> {len(resultat['contrats'])} contrats écrits dans {chemin.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

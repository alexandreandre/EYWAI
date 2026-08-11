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
    derniere_rubrique_70: str = ""
    base_courante: str = ""
    composant_type: str = ""

    for rubrique, valeur in lire_lignes(dossier / "reference.dsn"):
        if not rubrique.startswith("S21.G00.70."):
            # Sortie du groupe 70 : le prochain bloc 70 repart de zéro, même
            # s'il commence par un numéro supérieur au dernier vu.
            affiliation = None
            derniere_rubrique_70 = ""
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
            base_courante = ""
        elif rubrique == "S21.G00.30.014" and courant is not None:
            courant["departement_naissance"] = valeur
        elif rubrique == "S21.G00.30.015" and courant is not None:
            courant["pays_naissance"] = valeur
        elif rubrique == "S21.G00.40.002" and courant is not None:
            courant["statut"] = courant["statut"] or valeur
        elif rubrique.startswith("S21.G00.70.") and courant is not None:
            # La norme émet les rubriques d'un bloc par numéro croissant : un
            # numéro qui redescend (ou se répète) ouvre un nouveau bloc 70.
            # Le 70.004 n'est pas toujours présent — un bloc peut commencer
            # directement à 70.005 (vu chez le cabinet, deux affiliations).
            cle = {"004": "option", "005": "population", "012": "id_affiliation", "013": "id_contrat"}
            suffixe = rubrique.rsplit(".", 1)[-1]
            if suffixe in cle:
                if affiliation is None or suffixe <= derniere_rubrique_70:
                    affiliation = {}
                    courant["affiliations"].append(affiliation)
                affiliation[cle[suffixe]] = valeur
                derniere_rubrique_70 = suffixe
        elif rubrique == "S21.G00.30.025" and courant is not None:
            courant.setdefault("niveau_diplome_prepare", valeur)
        elif rubrique == "S21.G00.40.010" and courant is not None:
            courant.setdefault("date_fin_contrat", valeur)
        elif rubrique == "S21.G00.40.021" and courant is not None:
            courant.setdefault("motif_recours", valeur)
        elif rubrique == "S21.G00.50.007" and courant is not None:
            courant.setdefault("pas_type", valeur)
        elif rubrique == "S21.G00.50.008" and courant is not None:
            courant.setdefault("pas_identifiant", valeur)
        elif rubrique == "S21.G00.78.001":
            base_courante = valeur
        elif rubrique == "S21.G00.79.001":
            composant_type = valeur
        elif rubrique == "S21.G00.79.004" and courant is not None:
            # Composant « 01 » sous la base 03 : le SMIC retenu pour la
            # réduction générale de ce salarié.
            if base_courante == "03" and composant_type == "01":
                courant.setdefault("smic_retenu", valeur)

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

    return {
        "societe": societe,
        "dossier": dossier,
        "contrats": contrats,
        "profils": par_profil,
        "individus": individus,
        "nb": len(individus),
    }


def ecrire_salaries(resultat: dict) -> int:
    """Reprise par salarié dans input.json : affiliations, PAS, SMIC retenu.

    Ces trois données ne se déduisent d'aucun bulletin : les affiliations sont
    les contrats souscrits par chacun, l'identifiant PAS vient du compte rendu
    DGFiP, le SMIC retenu du calcul de réduction générale du cabinet — repris
    tel quel tant que le moteur ne range pas le sien dans `synthese_net`
    (`montant_smic_reduction_generale`, prioritaire quand il existera).
    """
    chemin = resultat["dossier"] / "input.json"
    donnees = json.loads(chemin.read_text())
    par_nir = {i["nir"]: i for i in resultat["individus"]}

    enrichis = 0
    for ligne in donnees["employees_data"]:
        employe = ligne.get("employee") or ligne
        nir = str(employe.get("nir") or employe.get("social_security_number") or "")
        repris = par_nir.get(nir.replace(" ", "")[:13])
        if not repris:
            continue
        if repris["affiliations"]:
            employe["affiliations_psc"] = repris["affiliations"]
        reprise = {}
        # Nés hors de France ou dans les DOM : le cabinet déclare 30.014='99'
        # (étranger) ou '97' (DOM, Mayotte comprise), et le pays en 30.015 —
        # 'FR' y compris pour les nés à l'étranger. Repris tels quels : ni le
        # département ni le pays ne se déduisent de la fiche dans ces cas.
        if repris.get("departement_naissance") in ("97", "99") and repris.get("pays_naissance"):
            reprise["departement_naissance"] = repris["departement_naissance"]
            reprise["pays_naissance"] = repris["pays_naissance"]
        if repris.get("motif_recours"):
            reprise["motif_recours"] = repris["motif_recours"]
        # Apprentis / alternants : niveau de diplôme préparé (30.025) et date
        # de fin prévisionnelle (40.010) quand la fiche ne la porte pas.
        if repris.get("niveau_diplome_prepare"):
            reprise["niveau_diplome_prepare"] = repris["niveau_diplome_prepare"]
        if repris.get("date_fin_contrat"):
            reprise["date_fin_contrat"] = repris["date_fin_contrat"]
        if repris.get("pas_type"):
            reprise["pas_type"] = repris["pas_type"]
        if repris.get("pas_identifiant"):
            reprise["pas_identifiant"] = repris["pas_identifiant"]
        if repris.get("smic_retenu"):
            reprise["smic_retenu"] = repris["smic_retenu"]
        if reprise:
            employe["dsn_reprise"] = reprise
        enrichis += 1
    chemin.write_text(json.dumps(donnees, ensure_ascii=False) + "\n", encoding="utf-8")
    return enrichis


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--societe")
    parser.add_argument("--json", action="store_true", help="config bloc 15 en JSON")
    parser.add_argument(
        "--ecrire",
        action="store_true",
        help="écrit organismes_complementaires dans le settings.json de chaque société",
    )
    parser.add_argument(
        "--ecrire-salaries",
        action="store_true",
        help="reprise par salarié dans input.json : affiliations, PAS, SMIC retenu",
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

        if args.ecrire_salaries:
            enrichis = ecrire_salaries(resultat)
            print(f"  -> {enrichis} salariés enrichis dans input.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

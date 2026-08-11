"""Porte la reprise DSN des jeux de conformité vers la base réelle.

Par salarié, depuis le dernier mois figé de chaque société
(`data/_dsn_conformance/<societe>/<mois>/input.json`) :

- ``affiliations_psc`` : les affiliations prévoyance/santé (blocs 70),
  reprises des DSN acceptées du cabinet — elles ne se déduisent de rien ;
- ``dsn_reprise`` : type et identifiant du taux PAS, SMIC retenu,
  département/pays de naissance, niveau de diplôme préparé, date de fin de
  contrat, motif de recours.

Écrit dans ``employees.specificites_paie`` sous ces deux clés, sans toucher
aux autres (mutuelle, prévoyance, prelevement_a_la_source…). Idempotent :
un salarié déjà à jour n'est pas réécrit.

SIMULATION PAR DÉFAUT. ``--apply`` exige ``--projet <ref>`` et refuse
d'écrire si le ref ne correspond pas au projet pointé par backend/.env —
qui pointe sur la PROD : ne pas appliquer sans l'avoir décidé.

    venv/bin/python scripts/dsn_reprise_loader.py                  # simule
    venv/bin/python scripts/dsn_reprise_loader.py --societe cartol
    venv/bin/python scripts/dsn_reprise_loader.py --apply --projet slleau…
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RACINE = Path(__file__).resolve().parents[2]
FIXTURES = RACINE / "data" / "_dsn_conformance"

SOCIETES = ["cartol", "colorplast", "comitech", "lewis", "mbc"]


def ref_projet() -> str:
    """Le ref du projet Supabase pointé par l'environnement du backend."""
    from app.core.database import supabase_url  # import tardif

    url = supabase_url or os.environ.get("SUPABASE_URL", "")
    return url.split("//")[-1].split(".")[0] if url else ""


def dernier_jeu(societe: str) -> Optional[Path]:
    dossiers = sorted(
        d for d in (FIXTURES / societe).glob("20*-*") if (d / "input.json").exists()
    )
    return dossiers[-1] if dossiers else None


def reprise_par_salarie(jeu: Path) -> List[Tuple[str, str, Dict[str, Any]]]:
    """[(employee_id, nir, {affiliations_psc, dsn_reprise})] du jeu."""
    donnees = json.loads((jeu / "input.json").read_text())
    sortie = []
    for ligne in donnees.get("employees_data") or []:
        employe = ligne.get("employee") or ligne
        identifiant = str(employe.get("id") or "")
        nir = str(employe.get("nir") or "").replace(" ", "")
        charge: Dict[str, Any] = {}
        affiliations = employe.get("affiliations_psc")
        if isinstance(affiliations, list) and affiliations:
            charge["affiliations_psc"] = affiliations
        reprise = employe.get("dsn_reprise")
        if isinstance(reprise, dict) and reprise:
            charge["dsn_reprise"] = reprise
        if identifiant and charge:
            sortie.append((identifiant, nir, charge))
    return sortie


def traiter(societe: str, appliquer: bool) -> Tuple[int, int, int]:
    from app.core.database import supabase  # import tardif

    jeu = dernier_jeu(societe)
    if not jeu:
        print(f"{societe} : aucun jeu de conformité, ignoré")
        return 0, 0, 0

    salaries = reprise_par_salarie(jeu)
    if not salaries:
        print(f"{societe} {jeu.name} : aucune reprise dans le jeu, ignoré")
        return 0, 0, 0

    reponse = (
        supabase.table("employees")
        .select("id,nir,specificites_paie")
        .in_("id", [identifiant for identifiant, _, _ in salaries])
        .execute()
    )
    en_base = {ligne["id"]: ligne for ligne in (reponse.data or [])}

    a_jour = ecrits = absents = 0
    for identifiant, nir, charge in salaries:
        ligne = en_base.get(identifiant)
        if not ligne:
            print(f"  ABSENT   {societe} {identifiant} (NIR {nir[:7]}…)")
            absents += 1
            continue
        nir_base = str(ligne.get("nir") or "").replace(" ", "")
        if nir and nir_base and nir_base[:13] != nir[:13]:
            print(f"  NIR ≠    {societe} {identifiant} : jeu {nir[:7]}… base {nir_base[:7]}… — non écrit")
            absents += 1
            continue
        specificites = ligne.get("specificites_paie") or {}
        if not isinstance(specificites, dict):
            specificites = {}
        if all(specificites.get(cle) == valeur for cle, valeur in charge.items()):
            a_jour += 1
            continue
        nouvelles = {**specificites, **charge}
        ecrits += 1
        if appliquer:
            supabase.table("employees").update(
                {"specificites_paie": nouvelles}
            ).eq("id", identifiant).execute()
        else:
            details = ", ".join(sorted(charge))
            print(f"  À ÉCRIRE {societe} {identifiant} ({details})")
    verbe = "écrits" if appliquer else "à écrire"
    print(
        f"{societe} {jeu.name} : {len(salaries)} repris — {ecrits} {verbe}, "
        f"{a_jour} déjà à jour, {absents} non appariés"
    )
    return ecrits, a_jour, absents


def traiter_organismes(societe: str, appliquer: bool) -> int:
    """Porte le bloc 15 (settings.json local) vers company_dsn_settings.

    Exige la colonne ``organismes_complementaires`` (migration
    20260811170000). L'ordre 15.005 fait partie de la donnée : les 70.013
    des salariés le référencent.
    """
    from app.core.database import supabase  # import tardif
    from app.modules.dsn_export.infrastructure import settings_repository

    chemin = FIXTURES / societe / "settings.json"
    if not chemin.exists():
        print(f"{societe} : pas de settings.json local, ignoré")
        return 0
    organismes = json.loads(chemin.read_text()).get("organismes_complementaires") or []
    if not organismes:
        print(f"{societe} : pas d'organismes dans le settings.json, ignoré")
        return 0

    nom = json.loads((dernier_jeu(societe) / "input.json").read_text())["company_name"]
    reponse = (
        supabase.table("companies").select("id").eq("company_name", nom).execute()
    )
    lignes = reponse.data or []
    if not lignes:
        print(f"{societe} : société «{nom}» introuvable en base, ignoré")
        return 0
    company_id = lignes[0]["id"]

    parametrage = settings_repository.charger(company_id)
    if parametrage.organismes_complementaires == organismes:
        print(f"{societe} : bloc 15 déjà à jour ({len(organismes)} contrats)")
        return 0
    parametrage.organismes_complementaires = organismes
    if appliquer:
        settings_repository.enregistrer(company_id, parametrage)
        print(f"{societe} : {len(organismes)} contrats du bloc 15 écrits")
    else:
        print(f"{societe} : {len(organismes)} contrats du bloc 15 À ÉCRIRE")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--societe", choices=SOCIETES)
    parser.add_argument(
        "--organismes",
        action="store_true",
        help="porte aussi le bloc 15 des settings.json vers company_dsn_settings",
    )
    parser.add_argument("--apply", action="store_true", help="écrit en base (simulation sinon)")
    parser.add_argument(
        "--projet",
        help="ref du projet Supabase attendu ; obligatoire avec --apply, "
        "refus si l'environnement pointe ailleurs",
    )
    args = parser.parse_args()

    ref = ref_projet()
    print(f"Projet Supabase pointé par l'environnement : {ref or 'inconnu'}")
    if args.apply:
        if not args.projet:
            print("--apply exige --projet <ref> : refus d'écrire sans cible explicite.")
            return 1
        if args.projet != ref:
            print(f"Refus : --projet {args.projet} ≠ environnement {ref}.")
            return 1
    else:
        print("SIMULATION — rien ne sera écrit (--apply --projet <ref> pour écrire).\n")

    total = (0, 0, 0)
    for societe in [args.societe] if args.societe else SOCIETES:
        resultat = traiter(societe, args.apply)
        total = tuple(a + b for a, b in zip(total, resultat))
        if args.organismes:
            traiter_organismes(societe, args.apply)
    ecrits, a_jour, absents = total
    verbe = "écrits" if args.apply else "à écrire"
    print(f"\nTotal : {ecrits} {verbe}, {a_jour} déjà à jour, {absents} non appariés")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

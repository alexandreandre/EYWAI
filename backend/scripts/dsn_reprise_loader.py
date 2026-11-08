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

SOCIETES = ["cartol", "colorplast", "comitech", "lewis", "maji", "mbc", "zone"]

#: Dossier de données -> nom exact en base (MAJI et Zone 404 n'ont pas de jeu).
NOMS = {
    "cartol": "Cartol Industrie",
    "colorplast": "Colorplast",
    "comitech": "Comitech Composite",
    "lewis": "LEWIS",
    "maji": "MAJI",
    "mbc": "Mont Blanc Composite",
    "zone": "Zone 404 Mars",
}


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


#: Rubriques du bloc 15 et leur clé dans company_dsn_settings.organismes_complementaires.
_BLOC_15 = {
    "S21.G00.15.001": "reference",
    "S21.G00.15.002": "organisme",
    "S21.G00.15.003": "delegataire",
    "S21.G00.15.004": "nature",
    "S21.G00.15.005": "ordre",
}


def organismes_du_jeu(jeu: Path) -> List[Dict[str, str]]:
    """Le bloc 15 de la DSN de référence du jeu, celle des affiliations.

    Les 70.013 des salariés désignent un contrat par son ordre 15.005 : le bloc
    15 doit venir de la même DSN, le cabinet pouvant réordonner ses contrats
    d'un mois à l'autre. Sans DSN de référence, rien (pas de settings.json
    d'un autre mois).
    """
    from app.modules.dsn_export.domain.conformance import lire_rubriques

    chemin = jeu / "reference.dsn"
    if not chemin.exists():
        return []
    organismes: List[Dict[str, str]] = []
    for code, valeur in lire_rubriques(chemin.read_bytes()):
        if code == "S21.G00.15.001":
            organismes.append({})
        if code in _BLOC_15 and organismes:
            organismes[-1][_BLOC_15[code]] = valeur
    return organismes


def organismes_de_la_dsn(chemin: Path) -> List[Dict[str, str]]:
    """Le bloc 15 d'une DSN du cabinet, avec l'ordre que ses 70.013 désignent."""
    from app.modules.dsn_export.domain.conformance import lire_rubriques

    organismes: List[Dict[str, str]] = []
    for code, valeur in lire_rubriques(chemin.read_bytes()):
        if code == "S21.G00.15.001":
            organismes.append({})
        if code in _BLOC_15 and organismes:
            organismes[-1][_BLOC_15[code]] = valeur
    return organismes


def reprise_depuis_dsn(chemin: Path) -> List[Tuple[str, Dict[str, Any]]]:
    """[(NIR sur 13, {affiliations_psc, dsn_reprise})] d'une DSN du cabinet.

    Lit la DSN elle-même : pas besoin de jeu figé, et le mois est celui qu'on
    choisit. Un salarié déclaré sur deux contrats le même mois n'a qu'une
    fiche : sa date de fin et son motif, propres à un contrat, ne sont pas repris.
    """
    from scripts.dsn_deriver_psc import lire_dsn, reprise_de

    sortie: List[Tuple[str, Dict[str, Any]]] = []
    for individu in lire_dsn(chemin)[1]:
        charge: Dict[str, Any] = {}
        if individu["affiliations"]:
            charge["affiliations_psc"] = individu["affiliations"]
        reprise = reprise_de(individu)
        if individu.get("nb_contrats", 0) > 1:
            reprise.pop("date_fin_contrat", None)
            reprise.pop("motif_recours", None)
        if reprise:
            charge["dsn_reprise"] = reprise
        if charge:
            sortie.append((individu["nir"].replace(" ", "")[:13], charge))
    return sortie


def planifier(
    employes: List[Dict[str, Any]], reprises: List[Tuple[str, Dict[str, Any]]]
) -> Dict[str, Any]:
    """Apparie par NIR, dans une seule société, et dit ce qu'il y a à écrire.

    Un NIR porté par deux fiches n'est pas tranché : aucune des deux n'est
    écrite. Les autres clés de ``specificites_paie`` sont conservées.
    """
    par_nir: Dict[str, List[Dict[str, Any]]] = {}
    for employe in employes:
        nir = str(employe.get("nir") or "").replace(" ", "")[:13]
        if nir:
            par_nir.setdefault(nir, []).append(employe)
    plan: Dict[str, Any] = {"ecritures": [], "a_jour": 0, "absents": 0, "ambigus": 0}
    for nir, charge in reprises:
        fiches = par_nir.get(nir) or []
        if not fiches:
            plan["absents"] += 1
            continue
        if len(fiches) > 1:
            plan["ambigus"] += 1
            continue
        specificites = fiches[0].get("specificites_paie")
        specificites = specificites if isinstance(specificites, dict) else {}
        if all(specificites.get(cle) == valeur for cle, valeur in charge.items()):
            plan["a_jour"] += 1
            continue
        plan["ecritures"].append((fiches[0], {**specificites, **charge}, charge))
    return plan


def id_societe(societe: str) -> Optional[str]:
    from app.core.database import supabase  # import tardif

    lignes = (
        supabase.table("companies").select("id").eq("company_name", NOMS[societe]).execute().data
        or []
    )
    return lignes[0]["id"] if lignes else None


def chemin_dsn(societe: str, mois: str) -> Path:
    return RACINE / "data" / societe / "dsn" / f"{mois}.dsn"


def traiter_dsn(societe: str, mois: str, appliquer: bool) -> Tuple[int, int, int]:
    """Comme ``traiter``, mais depuis la DSN du cabinet du mois demandé."""
    from app.core.database import supabase  # import tardif

    chemin = chemin_dsn(societe, mois)
    company_id = id_societe(societe)
    if not chemin.exists() or not company_id:
        print(f"{societe} {mois} : DSN ou société introuvable, ignoré")
        return 0, 0, 0
    employes = (
        supabase.table("employees")
        .select("id,nir,specificites_paie")
        .eq("company_id", company_id)
        .execute()
        .data
        or []
    )
    plan = planifier(employes, reprise_depuis_dsn(chemin))
    for fiche, nouvelles, charge in plan["ecritures"]:
        if appliquer:
            supabase.table("employees").update({"specificites_paie": nouvelles}).eq(
                "id", fiche["id"]
            ).execute()
        else:
            print(f"  À ÉCRIRE {societe} {fiche['id']} ({', '.join(sorted(charge))})")
    non_apparies = plan["absents"] + plan["ambigus"]
    print(
        f"{societe} {mois} : {len(plan['ecritures'])} "
        f"{'écrits' if appliquer else 'à écrire'}, {plan['a_jour']} déjà à jour, "
        f"{plan['absents']} sans fiche, {plan['ambigus']} NIR ambigus"
    )
    return len(plan["ecritures"]), plan["a_jour"], non_apparies


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


def traiter_organismes(societe: str, appliquer: bool, mois: Optional[str] = None) -> int:
    """Porte le bloc 15 vers company_dsn_settings.

    Depuis la DSN du cabinet de ``mois`` si donné, sinon de la DSN de référence
    du jeu : toujours la même DSN que les affiliations.

    Exige la colonne ``organismes_complementaires`` (migration
    20260811170000). L'ordre 15.005 fait partie de la donnée : les 70.013
    des salariés le référencent.
    """
    from app.core.database import supabase  # import tardif
    from app.modules.dsn_export.infrastructure import settings_repository

    if mois:
        chemin = chemin_dsn(societe, mois)
        organismes = organismes_de_la_dsn(chemin) if chemin.exists() else []
    else:
        jeu = dernier_jeu(societe)
        organismes = organismes_du_jeu(jeu) if jeu else []
    if not organismes:
        print(f"{societe} : pas de bloc 15 dans la DSN de référence, ignoré")
        return 0

    company_id = id_societe(societe)
    if not company_id:
        print(f"{societe} : société «{NOMS[societe]}» introuvable en base, ignoré")
        return 0

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
        help="porte aussi le bloc 15 de la DSN du jeu vers company_dsn_settings",
    )
    parser.add_argument(
        "--mois",
        help="AAAA-MM : lit la DSN du cabinet de ce mois plutôt que le dernier jeu figé",
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
        resultat = (
            traiter_dsn(societe, args.mois, args.apply)
            if args.mois
            else traiter(societe, args.apply)
        )
        total = tuple(a + b for a, b in zip(total, resultat))
        if args.organismes:
            traiter_organismes(societe, args.apply, args.mois)
    ecrits, a_jour, absents = total
    verbe = "écrits" if args.apply else "à écrire"
    print(f"\nTotal : {ecrits} {verbe}, {a_jour} déjà à jour, {absents} non appariés")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

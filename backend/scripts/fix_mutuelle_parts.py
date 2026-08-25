"""Rétablit la part patronale des mutuelles (6 sociétés).

Contexte
--------
L'import DSN dépose la cotisation mutuelle **totale** dans la part salariale et
laisse la part patronale à zéro. Résultat : 159 salariés actifs se voient
retenir le double de ce que le cabinet leur retient réellement, et la part
patronale — un avantage soumis à CSG — manque au net imposable.

Le rapprochement est arithmétique, pas approximatif. Les bulletins du cabinet
donnent les deux parts, et leur somme est exactement le montant qu'EYWAI porte
au salarié :

    Cartol  EMU1 Isolé            29,64 + 29,63 = 59,27
            EMU2 Isolé + enfants  89,81 + 29,94 = 119,75
            EMU3 Couple           88,61 + 29,54 = 118,15
            EMU4 Famille         158,25 + 29,99 = 188,24
    LEWIS   EMUT Mutuelle         58,03 + 58,03 = 116,06

Chez Cartol la part patronale est quasi fixe (~29,6 €) quelle que soit la
formule : l'employeur finance l'équivalent de l'isolé, le surcoût familial reste
au salarié. Ce n'est PAS un 50/50 — ne pas généraliser depuis LEWIS, qui l'est.

Ce que fait le script
---------------------
1. crée (ou aligne) un type de mutuelle par formule réelle, avec les deux parts ;
2. rattache chaque salarié à sa formule — par matricule d'après les bulletins,
   à défaut par égalité entre son montant actuel et le total d'une formule ;
3. laisse intact, et liste, tout ce qu'il ne sait pas trancher.

Les montants proratisés (mois partiel) ne matchent aucun total : ils sont
rattachés par matricule quand le bulletin existe, sinon signalés. Rattacher un
salarié à sa formule est le bon geste — c'est au moteur de proratiser.

Usage
-----
    python scripts/fix_mutuelle_parts.py                    # simulation
    python scripts/fix_mutuelle_parts.py --apply            # écriture + sauvegarde
    python scripts/fix_mutuelle_parts.py --revert FICHIER   # restauration
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import settings
from app.core.database import supabase

RACINE = Path(__file__).resolve().parents[2]
DATA = RACINE / "data"
SAUVEGARDES = DATA / "_backups"

# société EYWAI → dossier data/ portant ses bulletins
SOCIETES = {
    "Cartol Industrie": "cartol",
    "LEWIS": "lewis",
    "Mont Blanc Composite": "mbc",
    "Comitech Composite": "comitech",
    "MAJI": "maji",
    "Zone 404 Mars": "zone",
}

# ATTENTION : le code EMU n'a PAS le même sens d'une société à l'autre. EMU3 est
# « Couple » chez Cartol et « GAN MUTUELLE ISOLE » chez Comitech. Tout ce qui
# qualifie une formule se déduit donc de son libellé, jamais de son code.

TOLERANCE = 0.01


# ----- lecture des grilles -----


def _grilles_disponibles(dossier: str, periode: str) -> list[Path]:
    """CSV de grilles jusqu'au mois demandé, du plus ancien au plus récent."""
    dossier_ref = DATA / dossier / "referentiel"
    fichiers = [
        f for f in sorted(dossier_ref.glob("mutuelles-*.csv"))
        if f.stem <= f"mutuelles-{periode}"
    ]
    if not fichiers:
        raise SystemExit(
            f"Aucune grille jusqu'à {periode} dans "
            f"{dossier_ref.relative_to(RACINE)}\n"
            "Lancer d'abord scripts/extraire_mutuelles_bulletins.py"
        )
    return fichiers


def charger_grilles(dossier: str, periode: str) -> dict[str, dict]:
    """code EMU → {libelle, parts, total}, d'après le mois le plus récent connu.

    Toutes les sociétés n'ont pas un bulletin pour chaque mois : MAJI et
    Zone 404 n'en ont que jusqu'en mai. On prend le plus récent disponible.
    """
    chemin = _grilles_disponibles(dossier, periode)[-1]
    grilles: dict[str, dict] = {}
    with chemin.open(encoding="utf-8") as f:
        for ligne in csv.DictReader(f, delimiter=";"):
            if not ligne["code"]:
                continue  # salarié sans mutuelle : pas une grille
            grilles[ligne["code"]] = {
                "code": ligne["code"],
                "libelle": ligne["libelle"],
                "part_salariale": float(ligne["part_salariale"]),
                "part_patronale": float(ligne["part_patronale"]),
                "total": float(ligne["total"]),
            }
    return grilles


def charger_affectations(
    dossier: str, periode: str
) -> tuple[dict[str, str], set[str]]:
    """(matricule → code EMU, matricules vus au bulletin).

    Un matricule connu mais absent des affectations n'a **aucune** mutuelle au
    cabinet : si EYWAI lui en retient une, ce n'est pas une mutuelle.

    Un salarié entré ou sorti en cours d'année n'a pas de ligne mutuelle sur le
    mois de référence : son bulletin d'un autre mois la porte. On part du mois
    demandé et on remonte le temps — le plus récent gagne.
    """
    affectations: dict[str, str] = {}
    connus: set[str] = set()
    for chemin in _grilles_disponibles(dossier, periode):  # récents en dernier
        with chemin.open(encoding="utf-8") as f:
            for ligne in csv.DictReader(f, delimiter=";"):
                connus.add(ligne["matricule"])
                if ligne["code"]:
                    affectations[ligne["matricule"]] = ligne["code"]
    return affectations, connus


# ----- état actuel en base -----


# Préfixes que le cabinet répète dans chaque libellé et qui n'apprennent rien.
BRUIT = re.compile(r"^(GAN\s+)?(MUTUELLE|MUT\.?|Mut\.?)\s*", re.IGNORECASE)


def formule_lisible(grille: dict) -> str:
    """« GAN Mut Salarié+conjoint » → « Salarié + conjoint »."""
    texte = BRUIT.sub("", grille["libelle"]).strip()
    texte = re.sub(r"\s*\+\s*", " + ", texte)
    texte = texte.replace("( + )", "(+)")  # « 2enfants (+) » reste compact
    if texte.isupper():
        texte = texte.lower()
    texte = texte[:1].upper() + texte[1:]
    return texte.replace("Isole", "Isolé")


def pack_couverture(grille: dict) -> str:
    """Déduit le pack du libellé — le code EMU n'est pas portable entre sociétés."""
    texte = grille["libelle"].lower()
    a_conjoint = "conjoint" in texte or "couple" in texte
    a_enfant = "enfant" in texte or "famille" in texte
    if a_conjoint and not a_enfant:
        return "duo"
    if a_enfant:
        return "famille"
    if "isole" in texte or "isolé" in texte or "salarié" in texte:
        return "isole"
    return "autre"


def libelle_cible(grille: dict) -> str:
    formule = formule_lisible(grille)
    montants = (
        f"{grille['part_salariale']:.2f}€ / {grille['part_patronale']:.2f}€"
    )
    return f"Mutuelle {formule} {montants}" if formule else f"Mutuelle {montants}"


def etat_societe(company_id: str) -> tuple[list[dict], list[dict]]:
    types = (
        supabase.table("company_mutuelle_types")
        .select("*")
        .eq("company_id", company_id)
        .execute()
        .data
        or []
    )
    salaries = (
        supabase.table("employees")
        .select("id, matricule, first_name, last_name, employment_status")
        .eq("company_id", company_id)
        .execute()
        .data
        or []
    )
    liens = (
        supabase.table("employee_mutuelle_types")
        .select("id, employee_id, mutuelle_type_id")
        .in_("employee_id", [s["id"] for s in salaries])
        .execute()
        .data
        or []
    ) if salaries else []
    for s in salaries:
        s["lien"] = next(
            (l for l in liens if l["employee_id"] == s["id"]), None
        )
    return types, salaries


def choisir_code(
    salarie: dict,
    type_actuel: dict | None,
    affectations: dict[str, str],
    connus: set[str],
    grilles: dict[str, dict],
) -> tuple[str | None, str]:
    """Retourne (code EMU, motif). Code None = on ne touche pas."""
    matricule = (salarie.get("matricule") or "").strip()
    if matricule in affectations:
        return affectations[matricule], "bulletin"

    if matricule in connus:
        montant = float((type_actuel or {}).get("montant_salarial") or 0)
        return None, (
            f"AUCUNE mutuelle au bulletin — EYWAI retient {montant:.2f} € "
            "(prévoyance rangée en mutuelle ?)"
        )

    if type_actuel:
        actuel = float(type_actuel.get("montant_salarial") or 0)
        for code, grille in grilles.items():
            if abs(actuel - grille["total"]) <= TOLERANCE:
                return code, "total identique"
        if actuel:
            return None, f"montant {actuel:.2f} € hors grille (mois partiel ?)"
    return None, "aucune mutuelle en base"


# ----- écriture -----


def appliquer(periode: str, ecrire: bool) -> int:
    print(f"Base cible : {settings.SUPABASE_URL}")
    print(f"Mode       : {'ÉCRITURE' if ecrire else 'simulation'}\n")

    sauvegarde: dict = {"periode": periode, "societes": {}}
    residus: list[str] = []
    total_rattaches = 0

    societes = (
        supabase.table("companies")
        .select("id, company_name")
        .in_("company_name", list(SOCIETES))
        .execute()
        .data
        or []
    )

    for societe in sorted(societes, key=lambda c: c["company_name"]):
        nom = societe["company_name"]
        dossier = SOCIETES[nom]
        grilles = charger_grilles(dossier, periode)
        affectations, connus = charger_affectations(dossier, periode)
        types, salaries = etat_societe(societe["id"])
        par_id = {t["id"]: t for t in types}

        print(f"=== {nom} ===")

        # 1. un type par formule réelle
        cibles: dict[str, str] = {}
        types_crees: list[dict] = []
        for code, grille in sorted(grilles.items()):
            libelle = libelle_cible(grille)
            existant = next((t for t in types if t["libelle"] == libelle), None)
            payload = {
                "company_id": societe["id"],
                "libelle": libelle,
                "montant_salarial": grille["part_salariale"],
                "montant_patronal": grille["part_patronale"],
                "part_patronale_soumise_a_csg": True,
                "pack_couverture": pack_couverture(grille),
                "statut_categoriel": "tous",
                "is_active": True,
                "source": "dsn_import",
                "note": f"Grille cabinet {code} — bulletins {periode}",
            }
            if existant:
                cibles[code] = existant["id"]
                print(f"  = {libelle}")
                continue
            if ecrire:
                cree = (
                    supabase.table("company_mutuelle_types")
                    .insert(payload)
                    .execute()
                    .data[0]
                )
                cibles[code] = cree["id"]
                types_crees.append({"id": cree["id"]})
            else:
                cibles[code] = f"(nouveau {code})"
            print(f"  + {libelle}")

        # 2. rattachement des salariés
        avant: list[dict] = []
        rattaches = 0
        for salarie in sorted(salaries, key=lambda s: s.get("matricule") or ""):
            lien = salarie["lien"]
            actuel = par_id.get(lien["mutuelle_type_id"]) if lien else None
            code, motif = choisir_code(salarie, actuel, affectations, connus, grilles)
            etiquette = (
                f"{salarie.get('matricule') or '?':<12} "
                f"{salarie['last_name']} {salarie['first_name']}"
            )
            if code is None:
                if actuel:
                    residus.append(f"  {nom:18} {etiquette} — {motif}")
                continue
            if actuel and actuel["id"] == cibles.get(code):
                continue  # déjà bon
            rattaches += 1
            avant.append(
                {
                    "lien_id": lien["id"] if lien else None,
                    "employee_id": salarie["id"],
                    "mutuelle_type_id": lien["mutuelle_type_id"] if lien else None,
                }
            )
            if not ecrire:
                continue
            if lien:
                supabase.table("employee_mutuelle_types").update(
                    {"mutuelle_type_id": cibles[code]}
                ).eq("id", lien["id"]).execute()
            else:
                supabase.table("employee_mutuelle_types").insert(
                    {"employee_id": salarie["id"], "mutuelle_type_id": cibles[code]}
                ).execute()

        total_rattaches += rattaches
        print(f"  → {rattaches} salariés rattachés à leur formule\n")
        sauvegarde["societes"][nom] = {
            "types_crees": types_crees,
            "liens_avant": avant,
        }

    if residus:
        print(f"À trancher à la main ({len(residus)}) :")
        for ligne in residus:
            print(ligne)
        print()

    print(f"Total rattaché : {total_rattaches}")

    if ecrire:
        SAUVEGARDES.mkdir(parents=True, exist_ok=True)
        horodatage = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        fichier = SAUVEGARDES / f"mutuelle-parts-{horodatage}.json"
        fichier.write_text(
            json.dumps(sauvegarde, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Sauvegarde : {fichier.relative_to(RACINE)}")
        print(f"Restauration : --revert {fichier.relative_to(RACINE)}")
    else:
        print("Simulation — rien n'a été écrit. Relancer avec --apply.")
    return 0


def restaurer(chemin: str) -> int:
    sauvegarde = json.loads(Path(chemin).read_text(encoding="utf-8"))
    for nom, bloc in sauvegarde["societes"].items():
        for lien in bloc["liens_avant"]:
            if lien["lien_id"] and lien["mutuelle_type_id"]:
                supabase.table("employee_mutuelle_types").update(
                    {"mutuelle_type_id": lien["mutuelle_type_id"]}
                ).eq("id", lien["lien_id"]).execute()
            elif lien["lien_id"] is None:
                supabase.table("employee_mutuelle_types").delete().eq(
                    "employee_id", lien["employee_id"]
                ).execute()
        for cree in bloc["types_crees"]:
            supabase.table("company_mutuelle_types").delete().eq(
                "id", cree["id"]
            ).execute()
        print(f"{nom} : restauré")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="écrire en base")
    parser.add_argument("--revert", metavar="FICHIER", help="restaurer une sauvegarde")
    parser.add_argument("--periode", default="2026-07", help="AAAA-MM des bulletins")
    args = parser.parse_args()

    if args.revert:
        return restaurer(args.revert)
    return appliquer(args.periode, ecrire=args.apply)


if __name__ == "__main__":
    sys.exit(main())

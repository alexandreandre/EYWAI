"""Crée les formules de prévoyance des sept sociétés depuis les fiches (02/11/2026).

Personne ne saisit les formules à notre place : les fiches les portent déjà.
Dans chaque société, chaque jeu de lignes de prévoyance partagé par au moins
deux fiches d'une même catégorie (cadre, non-cadre) devient une formule
(`company_prevoyance_formules`), et ces fiches y sont reliées
(`specificites_paie.prevoyance.formule_id`). Un jeu porté par une seule fiche
reste « lignes saisies à la main ».

Rien ne change dans le calcul : les lignes des fiches ne bougent pas, et le
lien `formule_id` est hors de l'empreinte des bulletins (5f0481a3). L'écriture
n'a donc de sens qu'une fois ce code EN LIGNE (sinon le lien périmerait les
bulletins) et la migration 20261102120000 passée.

Libellé : « Prévoyance cadre » ou « Prévoyance non-cadre », suivi de A, B…
quand une catégorie a plusieurs jeux (le plus fréquent d'abord). La RH les
renomme à l'écran si elle veut.

Depuis backend/ :

    PYTHONPATH=. python -m scripts.creer_formules_prevoyance
        Simulation : rien n'est écrit (piège à écritures posé).

    PYTHONPATH=. python -m scripts.creer_formules_prevoyance --ecrire --empreinte <sha>
        Écrit, seulement si l'empreinte est celle de la simulation. Sauvegarde
        les fiches touchées dans data/_sauvegardes/, puis relit et contrôle.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.prevoyance_formules.domain.rules import cle_des_lignes
from app.shared.domain.employment_rules import is_cadre

MINIMUM_DE_FICHES = 2


def dossier_sauvegardes() -> Path:
    commun = subprocess.check_output(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=Path(__file__).resolve().parent,
        text=True,
    ).strip()
    return Path(commun).parent / "data" / "_sauvegardes"


def _specificites(fiche: dict[str, Any]) -> dict[str, Any]:
    brut = fiche.get("specificites_paie")
    if isinstance(brut, str):
        brut = json.loads(brut)
    return brut if isinstance(brut, dict) else {}


def lire() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    from app.core.database import supabase

    societes = supabase.table("companies").select("id, company_name").order("company_name").execute().data or []
    fiches = (
        supabase.table("employees")
        .select("id, company_id, statut, specificites_paie, updated_at")
        .execute()
        .data
        or []
    )
    try:
        formules = supabase.table("company_prevoyance_formules").select("*").execute().data or []
    except Exception:  # noqa: BLE001 — table pas encore créée : simulation seulement
        formules = []
    return societes, fiches, formules


def planifier(societes, fiches, formules) -> list[dict[str, Any]]:
    """Une entrée par formule à créer : société, catégorie, lignes, fiches."""
    existantes = {
        (f["company_id"], f["statut_categoriel"], cle_des_lignes(f.get("lignes"))) for f in formules if f.get("is_active")
    }
    groupes: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for fiche in fiches:
        prevoyance = _specificites(fiche).get("prevoyance")
        if not isinstance(prevoyance, dict) or not prevoyance.get("adhesion"):
            continue
        lignes = prevoyance.get("lignes_specifiques") or []
        if not lignes or prevoyance.get("formule_id"):
            continue
        categorie = "cadre" if is_cadre(fiche.get("statut")) else "non_cadre"
        groupes[(fiche["company_id"], categorie, cle_des_lignes(lignes))].append(fiche)
    plan: list[dict[str, Any]] = []
    noms = {s["id"]: s["company_name"] for s in societes}
    # Taux recalculés à l'import depuis des montants arrondis au centime (LEWIS :
    # 0,7296 % à 0,7312 % pour un contrat à 0,73 %) : un seul jeu, dont la
    # formule prend les taux les plus fréquents. Seules les fiches qui ont
    # exactement ces taux y sont reliées ; les autres sont comptées « à aligner ».
    familles: dict[tuple, list[tuple]] = defaultdict(list)
    for cle in groupes:
        familles[(cle[0], cle[1], _forme(cle[2]))].append(cle)
    par_categorie: dict[tuple, list[tuple]] = defaultdict(list)
    for (company_id, categorie, _), cles in familles.items():
        # Le plus fréquent ; à égalité, le taux le plus rond (0,73 % plutôt que 0,7301 %).
        cles.sort(key=lambda c: (-len(groupes[c]), _chiffres(c[2])))
        representant = cles[0]
        total = sum(len(groupes[c]) for c in cles)
        if total >= MINIMUM_DE_FICHES and representant not in existantes:
            par_categorie[(company_id, categorie)].append((representant, cles[1:]))
    for (company_id, categorie), jeux in sorted(par_categorie.items(), key=lambda x: (noms.get(x[0][0], ""), x[0][1])):
        jeux.sort(key=lambda j: -(len(groupes[j[0]]) + sum(len(groupes[c]) for c in j[1])))
        base = "Prévoyance cadre" if categorie == "cadre" else "Prévoyance non-cadre"
        for rang, (cle, proches) in enumerate(jeux):
            membres = groupes[cle]
            modele = _specificites(membres[0])["prevoyance"]["lignes_specifiques"]
            plan.append(
                {
                    "company_id": company_id,
                    "societe": noms.get(company_id, company_id),
                    "libelle": base if len(jeux) == 1 else f"{base} {chr(ord('A') + rang)}",
                    "statut_categoriel": categorie,
                    "lignes": [{k: v for k, v in l.items() if k != "id"} for l in modele],
                    "fiches": sorted((m["id"], m["updated_at"]) for m in membres),
                    "a_aligner": sum(len(groupes[c]) for c in proches),
                }
            )
    return plan


def _chiffres(cle: tuple) -> int:
    return sum(len(f"{taux:.10g}") for ligne in cle for taux in ligne[1:4])


def _forme(cle: tuple) -> tuple:
    """La clé des lignes, taux arrondis à 0,01 point : les jeux qui ne diffèrent que par l'arrondi."""
    return tuple(
        (ligne[0], *(round(t, 4) for t in ligne[1:4]), *ligne[4:]) for ligne in cle
    )


def empreinte(plan: list[dict[str, Any]]) -> str:
    brut = json.dumps(plan, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(brut.encode("utf-8")).hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ecrire", action="store_true")
    parser.add_argument("--empreinte")
    args = parser.parse_args()
    if args.ecrire and not args.empreinte:
        parser.error("--ecrire demande --empreinte <sha> : lancez d'abord la simulation.")
    if not args.ecrire:
        from scripts.verification_rgdu import piege

        piege.poser_le_piege()

    societes, fiches, formules = lire()
    plan = planifier(societes, fiches, formules)
    for entree in plan:
        libelles = ", ".join(str(l.get("libelle")) for l in entree["lignes"])
        taux = " / ".join(f"{float(l.get('salarial') or 0) * 100:g} %" for l in entree["lignes"])
        aligner = f", {entree['a_aligner']} à aligner (taux arrondis à l'import)" if entree["a_aligner"] else ""
        n = len(entree["fiches"])
        print(f"{entree['societe']} — {entree['libelle']} : {n} fiche{'s' if n > 1 else ''}{aligner} ; "
              f"lignes : {libelles} ; taux salarial : {taux}")
    seules = sum(
        1
        for f in fiches
        if (_specificites(f).get("prevoyance") or {}).get("adhesion")
        and (_specificites(f).get("prevoyance") or {}).get("lignes_specifiques")
        and not any(f["id"] == eid for e in plan for eid, _ in e["fiches"])
    )
    print(f"formules : {len(plan)} ; fiches reliées : {sum(len(e['fiches']) for e in plan)} ; "
          f"fiches laissées en lignes saisies à la main : {seules}")
    actuelle = empreinte(plan)
    print(f"empreinte : {actuelle}")
    if not args.ecrire:
        print("Simulation : rien n'a été écrit. Pour écrire (code et migration EN LIGNE d'abord) :")
        print(f"    PYTHONPATH=. python -m scripts.creer_formules_prevoyance --ecrire --empreinte {actuelle}")
        return 0
    if args.empreinte != actuelle:
        raise SystemExit("Les fiches ont changé depuis la simulation : rien n'est écrit. Relancez la simulation.")

    from app.core.database import supabase

    par_id = {f["id"]: f for f in fiches}
    dossier = dossier_sauvegardes()
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / f"formules-prevoyance-{datetime.now().astimezone():%Y%m%d-%H%M%S}.json"
    touchees = [par_id[eid] for e in plan for eid, _ in e["fiches"]]
    fichier.write_text(json.dumps(touchees, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"sauvegarde : {fichier}")
    for entree in plan:
        formule = (
            supabase.table("company_prevoyance_formules")
            .insert(
                {
                    "company_id": entree["company_id"],
                    "libelle": entree["libelle"],
                    "statut_categoriel": entree["statut_categoriel"],
                    "lignes": entree["lignes"],
                }
            )
            .execute()
            .data[0]
        )
        for eid, updated_at in entree["fiches"]:
            specificites = copy.deepcopy(_specificites(par_id[eid]))
            specificites["prevoyance"]["formule_id"] = formule["id"]
            r = (
                supabase.table("employees")
                .update({"specificites_paie": specificites})
                .eq("id", eid)
                .eq("updated_at", updated_at)
                .execute()
            )
            if len(r.data or []) != 1:
                raise SystemExit(f"Fiche {eid} modifiée entre la lecture et l'écriture : arrêt, voir {fichier}.")
            relue = _specificites(r.data[0])
            avant = _specificites(par_id[eid])
            if relue["prevoyance"].get("lignes_specifiques") != avant["prevoyance"].get("lignes_specifiques"):
                raise SystemExit(f"Fiche {eid} : lignes changées à l'écriture, voir {fichier}.")
        print(f"{entree['societe']} — {entree['libelle']} : créée, {len(entree['fiches'])} fiches reliées.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

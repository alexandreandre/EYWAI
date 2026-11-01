"""Reprise de la PPV dans la réduction générale de 2026 (Colorplast, Comitech).

La rémunération de la réduction générale est celle soumise à cotisations,
« majorée le cas échéant des montants de prime de partage de la valeur (PPV)
versés » (BOSS, réduction générale, § 170 et § 610 ; CSS L241-13, III ; copies
dans docs/reference/reduction-generale-2026/). Quadra l'applique : sur les DSN de
janvier à septembre 2026, la réduction déclarée vaut au centime
coefficient(SMIC, brut + PPV) × (brut + PPV), pour chaque salarié qui a reçu la
PPV de juillet et de septembre.

Le cumul repris de Quadra au 30/09 porte cette réduction, mais un brut sans la
PPV : sans reprise, la régularisation d'octobre la recalcule sans elle et prend
environ 1 132 € de réduction en trop (Colorplast 288,52 €, Comitech 843,68 €,
mesure du 01/11/2026).

La correction passe par la clé de reprise `brut_hors_reduction_generale`
(engine/calcul_reduction_generale.py) : elle retire un montant du brut de la
réduction ; négative, elle y ajoute la PPV. Elle ne vaut que pour l'année de la
reprise et s'efface en janvier. Les deux versements de 2026 sont faits ; le
moteur ne compte pas encore une PPV qu'il verserait lui-même (à corriger avant
la prochaine).

La PPV de chaque salarié se lit à l'exécution dans les DSN Quadra
(data/<société>/dsn/2026-MM.dsn, bloc 52, types 904 à 906, hors git), le salarié
retrouvé par son NIR. La clé `ppv_reduction_generale` garde le montant ajouté :
le script refuse de l'ajouter deux fois.

Depuis backend/ :

    PYTHONPATH=. python -m scripts.reprise_ppv_reduction
        Simulation : rien n'est écrit (piège à écritures posé).

    PYTHONPATH=. python -m scripts.reprise_ppv_reduction --ecrire --empreinte <sha>
        Écrit le cumul de septembre des salariés concernés, seulement si
        l'empreinte est celle de la simulation. Sauvegarde avant, relit après.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SOCIETES = {
    "dbe2b9f5-44dd-41bc-a625-36ed33d160f7": "colorplast",
    "12cd8c71-da13-43f9-9151-475c4d5e8812": "comitech",
}
ANNEE, MOIS_DE_REPRISE = 2026, 9
TYPES_PPV = {"904", "905", "906"}
CLE_BRUT_HORS = "brut_hors_reduction_generale"
CLE_TRACE = "ppv_reduction_generale"


def dossier_data() -> Path:
    """data/ du dépôt principal (hors git), même depuis un worktree."""
    commun = subprocess.check_output(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=Path(__file__).resolve().parent,
        text=True,
    ).strip()
    return Path(commun).parent / "data"


def ppv_par_nir(texte: str) -> dict[str, float]:
    """La PPV d'une DSN par NIR (13 caractères) : blocs 52 de type 904 à 906."""
    resultat: dict[str, float] = {}
    nir, type_prime = None, None
    for ligne in texte.splitlines():
        cle, _, valeur = ligne.partition(",")
        valeur = valeur.strip().strip("'")
        if cle == "S21.G00.30.001":
            nir, type_prime = valeur[:13], None
        elif cle == "S21.G00.52.001":
            type_prime = valeur
        elif cle == "S21.G00.52.002" and nir and type_prime in TYPES_PPV:
            resultat[nir] = round(resultat.get(nir, 0.0) + float(valeur or 0), 2)
    return resultat


def ppv_de_l_annee(societe: str) -> dict[str, float]:
    total: dict[str, float] = {}
    for mois in range(1, MOIS_DE_REPRISE + 1):
        chemin = dossier_data() / societe / "dsn" / f"{ANNEE}-{mois:02d}.dsn"
        if chemin.exists():
            for nir, montant in ppv_par_nir(chemin.read_text(encoding="latin-1")).items():
                total[nir] = round(total.get(nir, 0.0) + montant, 2)
    return total


def cumuls_ajustes(cumuls: dict[str, Any], ppv: float) -> dict[str, Any]:
    """Les cumuls de septembre, la PPV ajoutée au brut de la réduction. Arrête
    tout si elle l'est déjà."""
    if ppv <= 0:
        raise SystemExit("PPV nulle : rien à ajouter.")
    nouveaux = copy.deepcopy(cumuls)
    compteurs = nouveaux.setdefault("cumuls", {})
    if CLE_TRACE in compteurs:
        raise SystemExit(f"PPV déjà ajoutée ({compteurs[CLE_TRACE]} €) : rien n'est écrit.")
    compteurs[CLE_BRUT_HORS] = round(float(compteurs.get(CLE_BRUT_HORS) or 0.0) - ppv, 2)
    compteurs[CLE_TRACE] = round(ppv, 2)
    return nouveaux


def initiales(fiche: dict[str, Any]) -> str:
    return f"{(fiche.get('first_name') or '?')[:1]}.{(fiche.get('last_name') or '?')[:1]}.".upper()


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
    from app.core.database import supabase

    plan: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], float]] = []
    for company_id, societe in SOCIETES.items():
        ppv = ppv_de_l_annee(societe)
        fiches = supabase.table("employees").select("id, first_name, last_name, nir").eq("company_id", company_id).execute().data or []
        for fiche in fiches:
            montant = ppv.get(str(fiche.get("nir") or "").replace(" ", "")[:13], 0.0)
            if not montant:
                continue
            lignes = (
                supabase.table("employee_schedules").select("id, cumuls, updated_at")
                .eq("employee_id", fiche["id"]).eq("year", ANNEE).eq("month", MOIS_DE_REPRISE)
                .execute().data or []
            )
            if len(lignes) != 1:
                print(f"{initiales(fiche)} ({societe}) : PPV {montant:.2f} €, pas de cumul de septembre — ignoré (sorti ?)")
                continue
            ligne = lignes[0]
            nouveaux = cumuls_ajustes(ligne["cumuls"] or {}, montant)
            plan.append((fiche, ligne, nouveaux, montant))
            avant = (ligne["cumuls"] or {}).get("cumuls", {}).get(CLE_BRUT_HORS)
            print(f"{initiales(fiche)} ({societe}) : PPV {montant:.2f} € ; {CLE_BRUT_HORS} {avant!r} -> "
                  f"{nouveaux['cumuls'][CLE_BRUT_HORS]!r}")
    etats = {f["id"]: {"ligne": l["id"], "cumuls": l["cumuls"], "updated_at": l["updated_at"]} for f, l, _, _ in plan}
    empreinte = hashlib.sha256(json.dumps(etats, sort_keys=True, default=str).encode()).hexdigest()
    print(f"{len(plan)} cumuls à ajuster ; empreinte : {empreinte}")
    if not args.ecrire:
        print("Simulation : rien n'a été écrit. Pour écrire :")
        print(f"    PYTHONPATH=. python -m scripts.reprise_ppv_reduction --ecrire --empreinte {empreinte}")
        return 0
    if args.empreinte != empreinte:
        raise SystemExit("Les cumuls ont changé depuis la simulation : rien n'est écrit. Relancez la simulation.")
    sauvegarde = dossier_data() / "_sauvegardes" / f"ppv-reduction-{datetime.now().astimezone():%Y%m%d-%H%M%S}.json"
    sauvegarde.parent.mkdir(parents=True, exist_ok=True)
    sauvegarde.write_text(json.dumps(etats, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"sauvegarde : {sauvegarde}")
    for fiche, ligne, nouveaux, _ in plan:
        reponse = (
            supabase.table("employee_schedules").update({"cumuls": nouveaux})
            .eq("id", ligne["id"]).eq("updated_at", ligne["updated_at"]).execute()
        )
        if len(reponse.data or []) != 1:
            raise SystemExit(f"{initiales(fiche)} : cumul modifié entre la lecture et l'écriture, arrêt.")
        relu = supabase.table("employee_schedules").select("cumuls").eq("id", ligne["id"]).execute().data[0]["cumuls"]
        if relu != nouveaux:
            raise SystemExit(f"{initiales(fiche)} : relecture différente de l'attendu, voir {sauvegarde}.")
        print(f"{initiales(fiche)} : écrit et relu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

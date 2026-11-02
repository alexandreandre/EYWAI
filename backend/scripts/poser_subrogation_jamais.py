"""Pose « Jamais — IJSS versées au salarié » chez MAJI, Zone 404 et Mont Blanc.

Pourquoi : le tableau de la RH relayé par Elsa le 28/10/2026 dit que MAJI et
Zone 404 n'ont pas de subrogation (maintien légal) et que Mont Blanc n'en a pas
non plus (maintien de la convention). En base, MAJI et Zone 404 n'ont pas de
ligne (le moteur prend alors « when_maintien », subrogation dès que le maintien
s'applique) et Mont Blanc est réglée « when_maintien ». Colorplast et Comitech
sont déjà à « never ».

Ce qui change, et seulement ça :
- `subrogation_mode` → « never » : la caisse paie les IJSS au salarié ;
- `deduire_ijss_sans_subrogation` → true : Martine ne verse que le complément,
  IJSS des jours maintenus déduites (Code du travail D1226-5), comme Colorplast
  et Comitech. Sans ce second réglage, le salarié toucherait le salaire garanti
  en entier ET les IJSS de la caisse. Seule Mont Blanc a une ligne à false ;
  MAJI et Zone 404 prennent déjà true par défaut.

L'écriture passe par la commande de l'écran « Maintien de salaire »
(`save_maintenance_settings`) : les autres réglages restent ceux d'aujourd'hui.
Sans ligne, le moteur lit les valeurs par défaut de `queries._defaults`, les
mêmes que les défauts de la table : créer la ligne ne change rien d'autre.

Bulletins : le réglage n'entre dans l'empreinte d'un bulletin que si le mois
(ou sa fenêtre) porte un arrêt typé. Le script compte ces bulletins ; au
02/11/2026 il n'y en a aucun dans les trois sociétés, donc aucun ne passe
« À recalculer ».

Depuis backend/ :

    PYTHONPATH=. python -m scripts.poser_subrogation_jamais
        Simulation : rien n'est écrit (piège à écritures posé). Affiche
        l'avant/après et l'empreinte.

    PYTHONPATH=. python -m scripts.poser_subrogation_jamais --ecrire --empreinte <sha>
        Écrit, seulement si l'empreinte est celle de la simulation. Sauvegarde
        les lignes d'avant dans data/_sauvegardes/, puis relit et contrôle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SOCIETES = {
    "113b2f33-82ec-4cec-8d3a-f16cda8f74f2": "MAJI",
    "03fb17a5-134b-4c6e-9927-2083370c44d4": "Zone 404",
    "b541df31-e964-485e-ac36-cf580633fd1d": "Mont Blanc",
}
CIBLE = {"subrogation_mode": "never", "deduire_ijss_sans_subrogation": True}
#: Ce qui bouge sans être un réglage.
_HORS_REGLAGE = frozenset({"id", "created_at", "updated_at"})


def dossier_sauvegardes() -> Path:
    """data/_sauvegardes du dépôt principal (hors git), même depuis un worktree."""
    commun = subprocess.check_output(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=Path(__file__).resolve().parent,
        text=True,
    ).strip()
    return Path(commun).parent / "data" / "_sauvegardes"


def lire_ligne(company_id: str) -> dict[str, Any] | None:
    from app.modules.maintenance_settings.infrastructure.repository import (
        maintenance_settings_repository,
    )

    return maintenance_settings_repository.get_by_company(company_id)


def reglage_lu_par_le_moteur(company_id: str) -> dict[str, Any]:
    from app.modules.maintenance_settings.application.queries import (
        get_maintenance_settings,
    )

    lu = get_maintenance_settings(company_id).model_dump(mode="json")
    return {k: v for k, v in lu.items() if k not in _HORS_REGLAGE}


def bulletins_avec_arret(company_id: str) -> list[str]:
    """Bulletins dont le mois ou le mois d'avant porte un arrêt typé au planning."""
    from app.core.database import supabase

    salaries = [
        r["id"]
        for r in (supabase.table("employees").select("id").eq("company_id", company_id).execute().data or [])
    ]
    if not salaries:
        return []
    mois_arret: set[tuple[str, int]] = set()
    for i in range(0, len(salaries), 50):
        lot = salaries[i : i + 50]
        lignes = (
            supabase.table("employee_schedules")
            .select("employee_id, year, month, planned_calendar")
            .in_("employee_id", lot)
            .execute()
            .data
            or []
        )
        for r in lignes:
            jours = ((r.get("planned_calendar") or {}).get("calendrier_prevu")) or []
            if isinstance(jours, list) and any(isinstance(j, dict) and j.get("arret_type") for j in jours):
                mois_arret.add((r["employee_id"], int(r["year"]) * 12 + int(r["month"])))
    touches: list[str] = []
    for i in range(0, len(salaries), 50):
        lot = salaries[i : i + 50]
        for b in (
            supabase.table("payslips").select("id, employee_id, year, month").in_("employee_id", lot).execute().data
            or []
        ):
            m = int(b["year"]) * 12 + int(b["month"])
            if (b["employee_id"], m) in mois_arret or (b["employee_id"], m - 1) in mois_arret:
                touches.append(str(b["id"]))
    return sorted(touches)


def empreinte(etats: dict[str, Any]) -> str:
    brut = json.dumps(etats, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(brut.encode("utf-8")).hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ecrire", action="store_true", help="écrire (sinon simulation)")
    parser.add_argument("--empreinte", help="empreinte affichée par la simulation (obligatoire avec --ecrire)")
    args = parser.parse_args()
    if args.ecrire and not args.empreinte:
        parser.error("--ecrire demande --empreinte <sha> : lancez d'abord la simulation.")
    if not args.ecrire:
        from scripts.verification_rgdu import piege

        piege.poser_le_piege()

    etats: dict[str, Any] = {}
    for cid, nom in SOCIETES.items():
        ligne = lire_ligne(cid)
        lu = reglage_lu_par_le_moteur(cid)
        apres = {**lu, **CIBLE}
        changes = {k: (lu.get(k), v) for k, v in apres.items() if lu.get(k) != v}
        touches = bulletins_avec_arret(cid)
        etats[cid] = {"ligne": ligne, "lu": lu, "bulletins_avec_arret": touches}
        print(f"{nom} : {'ligne existante' if ligne else 'pas de ligne (valeurs par défaut)'}")
        for k, (a, b) in changes.items():
            print(f"    {k} : {a!r} -> {b!r}")
        if not changes:
            print("    déjà réglée, rien à changer")
        print(
            f"    bulletins avec un arrêt dans la fenêtre : {len(touches)}"
            + (" — ils passeront « À recalculer »" if touches else "")
        )
    actuelle = empreinte(etats)
    print(f"empreinte : {actuelle}")

    if not args.ecrire:
        print("Simulation : rien n'a été écrit. Pour écrire :")
        print(f"    PYTHONPATH=. python -m scripts.poser_subrogation_jamais --ecrire --empreinte {actuelle}")
        return 0
    if args.empreinte != actuelle:
        raise SystemExit(
            "Un réglage ou un bulletin a changé depuis la simulation (empreinte différente) : "
            "rien n'est écrit. Relancez la simulation."
        )

    dossier = dossier_sauvegardes()
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / f"subrogation-jamais-{datetime.now().astimezone():%Y%m%d-%H%M%S}.json"
    fichier.write_text(json.dumps(etats, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"sauvegarde : {fichier}")

    from app.modules.maintenance_settings.application.commands import (
        save_maintenance_settings,
    )
    from app.modules.maintenance_settings.schemas.requests import (
        MaintenanceSettingsUpdate,
    )

    for cid, nom in SOCIETES.items():
        avant = etats[cid]["lu"]
        if all(avant.get(k) == v for k, v in CIBLE.items()):
            print(f"{nom} : déjà réglée.")
            continue
        save_maintenance_settings(cid, MaintenanceSettingsUpdate(**CIBLE))
        relu = reglage_lu_par_le_moteur(cid)
        attendu = {**avant, **CIBLE}
        if relu != attendu:
            ecarts = {k: (attendu.get(k), relu.get(k)) for k in set(attendu) | set(relu) if attendu.get(k) != relu.get(k)}
            raise SystemExit(f"{nom} : relecture différente de l'attendu {ecarts}, voir {fichier}.")
        print(f"{nom} : écrit et relu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

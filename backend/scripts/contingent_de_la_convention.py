"""Remet au contingent de la convention les sociétés réglées autrement (03/11/2026).

Audit du 02/11, n° 6 : Comitech (plasturgie) est réglée à 220 h, le défaut du
décret (D3121-24), au lieu des 130 h de sa convention (accord du 17/10/2000,
art. 4.4). Sans accord d'entreprise, c'est le contingent de la branche qui
s'applique (L3121-33). Ce script ne touche que les sociétés dont la
convention fixe un contingent (`contingent_legal_par_defaut`) et dont le
réglage en diffère.

À ne lancer que si aucun accord d'entreprise ne fixe un autre contingent :
la question des 360 h comptés par la RH est posée à Elsa. Un accord
trouvé plus tard se saisit à l'écran.

Après l'écriture, les compteurs de repos se recalculent à la prochaine
génération de chaque bulletin, pas avant.

Depuis backend/ :

    PYTHONPATH=. python -m scripts.contingent_de_la_convention
        Simulation : rien n'est écrit (piège à écritures posé).

    PYTHONPATH=. python -m scripts.contingent_de_la_convention --ecrire --empreinte <sha>
        Écrit, seulement si l'empreinte est celle de la simulation. Sauvegarde
        les réglages touchés dans data/_sauvegardes/, puis relit et contrôle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from app.modules.repos_compensateur.domain.contingent_rules import (
    LEGAL_COR_CONTINGENT_DEFAULT,
    contingent_legal_par_defaut,
)


def dossier_sauvegardes() -> Path:
    commun = subprocess.check_output(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=Path(__file__).resolve().parent,
        text=True,
    ).strip()
    return Path(commun).parent / "data" / "_sauvegardes"


def planifier(societes: list[dict[str, Any]], reglages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    par_societe = {str(r["company_id"]): r for r in reglages}
    plan = []
    for societe in societes:
        conventionnel = contingent_legal_par_defaut(societe.get("idcc"))
        if conventionnel == LEGAL_COR_CONTINGENT_DEFAULT:
            continue  # la convention ne fixe rien de plus que le décret
        reglage = par_societe.get(str(societe["id"]))
        if reglage is None:
            continue  # sans réglage, la société suit déjà sa convention
        actuel = float(reglage["legal_cor_contingent_hours"])
        if actuel == conventionnel:
            continue
        plan.append(
            {
                "company_id": str(societe["id"]),
                "societe": societe["company_name"],
                "avant": actuel,
                "apres": conventionnel,
                "updated_at": reglage.get("updated_at"),
            }
        )
    return plan


def empreinte(plan: list[dict[str, Any]]) -> str:
    texte = json.dumps(plan, sort_keys=True, default=str)
    return hashlib.sha256(texte.encode()).hexdigest()[:12]


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

    societes = supabase.table("companies").select("id, company_name, idcc").order("company_name").execute().data or []
    reglages = supabase.table("company_overtime_contingent_settings").select("*").execute().data or []
    plan = planifier(societes, reglages)
    for entree in plan:
        print(f"{entree['societe']} : contingent {entree['avant']:g} h → {entree['apres']:g} h (convention)")
    if not plan:
        print("Aucune société à corriger : toutes suivent leur convention.")
        return 0
    actuelle = empreinte(plan)
    print(f"empreinte : {actuelle}")
    if not args.ecrire:
        print("Simulation : rien n'a été écrit. Pour écrire :")
        print(f"    PYTHONPATH=. python -m scripts.contingent_de_la_convention --ecrire --empreinte {actuelle}")
        return 0
    if args.empreinte != actuelle:
        raise SystemExit("Les réglages ont changé depuis la simulation : rien n'est écrit. Relancez la simulation.")

    dossier = dossier_sauvegardes()
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / f"contingent-convention-{datetime.now().astimezone():%Y%m%d-%H%M%S}.json"
    touches = [r for r in reglages if str(r["company_id"]) in {e["company_id"] for e in plan}]
    fichier.write_text(json.dumps(touches, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"sauvegarde : {fichier}")
    for entree in plan:
        r = (
            supabase.table("company_overtime_contingent_settings")
            .update({"legal_cor_contingent_hours": entree["apres"], "updated_at": datetime.now().astimezone().isoformat()})
            .eq("company_id", entree["company_id"])
            .eq("updated_at", entree["updated_at"])
            .execute()
        )
        if len(r.data or []) != 1:
            raise SystemExit(f"{entree['societe']} : réglage modifié entre la lecture et l'écriture, voir {fichier}.")
        if float(r.data[0]["legal_cor_contingent_hours"]) != entree["apres"]:
            raise SystemExit(f"{entree['societe']} : relu {r.data[0]['legal_cor_contingent_hours']}, voir {fichier}.")
        print(f"{entree['societe']} : écrit et relu, {entree['apres']:g} h.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

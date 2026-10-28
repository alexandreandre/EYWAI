"""Débloque les fiches salariés que le formulaire refuse d'enregistrer, sans toucher à la paie.

Le formulaire de la fiche (`employeeProfileEditSchema.ts`) refuse un code
PCS-ESE qui n'a pas la forme « trois chiffres et une lettre minuscule »
(`^\\d{3}[a-z]$`). Une seule fiche en cours de Colorplast et de Comitech est
dans ce cas avec une valeur juste connue : l'usineur S.B. (Comitech) porte
« 9999 », repris tel quel des DSN Quadra de janvier à juin 2026 ; son collègue
au même libellé d'emploi (« Usineur », V.C.) y est déclaré en 623f.

Le PCS n'est lu par aucun calcul de bulletin (DSN et OETH seulement ; aucun
poste ECAP chez Comitech). Bulletins de septembre recalculés au bac à sable,
fiche actuelle contre fiche corrigée en mémoire : 0 écart au centime. Les
bulletins de S.B. sont tous repris de Quadra (« importe ») : aucun ne passe
« À recalculer ».

Les deux autres fiches refusées (Colorplast, X.P. et F.A., en onboarding) n'ont
ni date de naissance ni IBAN : aucune source ne les donne, le script ne les
touche pas — ils se saisissent sur la fiche depuis le contrat et le RIB.

Depuis backend/ :

    PYTHONPATH=. python -m scripts.completer_fiches_formulaire
        Simulation : rien n'est écrit (piège à écritures posé). Affiche
        l'avant/après de chaque clé et l'empreinte des fiches.

    PYTHONPATH=. python -m scripts.completer_fiches_formulaire --ecrire --empreinte <sha>
        Écrit, seulement si l'empreinte est celle de la simulation (la fiche et
        la liste de ses bulletins n'ont pas changé depuis). Sauvegarde les fiches
        en JSON dans data/_sauvegardes/ avant d'écrire, puis relit et contrôle.

Seules les clés listées dans CORRECTIONS sont modifiées, et seulement sur ces
fiches ; une valeur d'avant différente de celle attendue arrête tout.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

#: Même règle que le formulaire (`FORMAT_PCS_ESE`, frontend/src/constants/dsnFiche.ts).
FORMAT_PCS_ESE = re.compile(r"^\d{3}[a-z]$")


@dataclass(frozen=True)
class Correction:
    employee_id: str
    initiales: str
    societe: str
    #: Clé de `classification_conventionnelle` corrigée.
    cle: str
    avant: Any
    apres: Any
    source: str


CORRECTIONS: tuple[Correction, ...] = (
    Correction(
        employee_id="312226e9-aab5-4dad-a06c-28ec8f09a1d0",
        initiales="S.B.",
        societe="12cd8c71-da13-43f9-9151-475c4d5e8812",  # Comitech Composite
        cle="pcs",
        avant="9999",
        apres="623f",
        source=(
            "PCS-ESE du collègue au même emploi « Usineur » (V.C.), déclaré par "
            "Quadra en S21.G00.40.004 dans les DSN de janvier à juin 2026 ; "
            "S.B. y porte « 9999 », que le formulaire refuse."
        ),
    ),
)


def dossier_sauvegardes() -> Path:
    """data/_sauvegardes du dépôt principal (hors git), même depuis un worktree."""
    commun = subprocess.check_output(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=Path(__file__).resolve().parent,
        text=True,
    ).strip()
    return Path(commun).parent / "data" / "_sauvegardes"


def lire_fiche(employee_id: str) -> dict[str, Any]:
    from app.core.database import supabase

    rows = supabase.table("employees").select("*").eq("id", employee_id).execute().data or []
    if len(rows) != 1:
        raise SystemExit(f"Fiche {employee_id} introuvable (ou en double) : rien n'est écrit.")
    return rows[0]


def lire_bulletins(employee_id: str) -> list[dict[str, Any]]:
    from app.core.database import supabase

    rows = (
        supabase.table("payslips")
        .select("id, year, month, status, origine, updated_at")
        .eq("employee_id", employee_id)
        .execute()
        .data
        or []
    )
    return sorted(rows, key=lambda r: (r["year"], r["month"], r["id"]))


def empreinte(etats: dict[str, dict[str, Any]]) -> str:
    """Hash de chaque fiche entière et de la liste de ses bulletins."""
    texte = json.dumps(etats, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def classification_corrigee(fiche: dict[str, Any], corrections: list[Correction]) -> dict[str, Any]:
    """La classification de la fiche, seules les clés corrigées changées.

    Arrête tout si une valeur d'avant n'est pas celle attendue, si une valeur
    corrigée ne passe pas le formulaire, ou si une autre clé changerait.
    """
    origine = fiche.get("classification_conventionnelle")
    if not isinstance(origine, dict):
        raise SystemExit(f"{corrections[0].initiales} : classification absente, rien n'est écrit.")
    nouvelle = copy.deepcopy(origine)
    for c in corrections:
        if origine.get(c.cle) != c.avant:
            raise SystemExit(
                f"{c.initiales} : {c.cle} vaut {origine.get(c.cle)!r}, {c.avant!r} attendu — "
                "la fiche a changé, rien n'est écrit."
            )
        if c.cle == "pcs" and not FORMAT_PCS_ESE.match(str(c.apres)):
            raise SystemExit(f"{c.initiales} : {c.apres!r} ne passe pas le formulaire, rien n'est écrit.")
        nouvelle[c.cle] = c.apres
    changees = {k for k in set(origine) | set(nouvelle) if origine.get(k) != nouvelle.get(k)}
    attendues = {c.cle for c in corrections}
    if changees != attendues:
        raise SystemExit(f"Clés changées {sorted(changees)} au lieu de {sorted(attendues)} : rien n'est écrit.")
    return nouvelle


def par_fiche() -> dict[str, list[Correction]]:
    groupes: dict[str, list[Correction]] = {}
    for c in CORRECTIONS:
        groupes.setdefault(c.employee_id, []).append(c)
    return groupes


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

    groupes = par_fiche()
    fiches = {eid: lire_fiche(eid) for eid in groupes}
    etats = {eid: {"fiche": fiches[eid], "bulletins": lire_bulletins(eid)} for eid in groupes}
    actuelle = empreinte(etats)

    plan: dict[str, dict[str, Any]] = {}
    for eid, corrections in groupes.items():
        fiche = fiches[eid]
        if fiche.get("company_id") != corrections[0].societe:
            raise SystemExit(f"{corrections[0].initiales} : société inattendue, rien n'est écrit.")
        plan[eid] = classification_corrigee(fiche, corrections)
        calcules = [b for b in etats[eid]["bulletins"] if (b.get("origine") or "calcule") != "importe"]
        for c in corrections:
            print(f"{c.initiales} classification_conventionnelle.{c.cle} : {c.avant!r} -> {c.apres!r}")
            print(f"    source : {c.source}")
        print(
            f"    bulletins : {len(etats[eid]['bulletins'])}, dont {len(calcules)} calculés par Martine"
            + (" — ils passeront « À recalculer » (montants inchangés)" if calcules else "")
        )
    print(f"empreinte : {actuelle}")

    if not args.ecrire:
        print("Simulation : rien n'a été écrit. Pour écrire :")
        print(f"    PYTHONPATH=. python -m scripts.completer_fiches_formulaire --ecrire --empreinte {actuelle}")
        return 0

    if args.empreinte != actuelle:
        raise SystemExit(
            "Une fiche ou ses bulletins ont changé depuis la simulation (empreinte différente) : "
            "rien n'est écrit. Relancez la simulation et relisez l'avant/après."
        )

    dossier = dossier_sauvegardes()
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / f"fiches-formulaire-{datetime.now().astimezone():%Y%m%d-%H%M%S}.json"
    fichier.write_text(json.dumps(etats, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"sauvegarde : {fichier}")

    from app.core.database import supabase

    for eid, nouvelle in plan.items():
        fiche = fiches[eid]
        reponse = (
            supabase.table("employees")
            .update({"classification_conventionnelle": nouvelle})
            .eq("id", eid)
            .eq("updated_at", fiche["updated_at"])
            .execute()
        )
        if len(reponse.data or []) != 1:
            raise SystemExit(f"{groupes[eid][0].initiales} : fiche modifiée entre la lecture et l'écriture, arrêt.")
        relue = lire_fiche(eid)
        attendu = {k: v for k, v in fiche.items() if k not in ("classification_conventionnelle", "updated_at")}
        obtenu = {k: v for k, v in relue.items() if k not in ("classification_conventionnelle", "updated_at")}
        if relue.get("classification_conventionnelle") != nouvelle or attendu != obtenu:
            raise SystemExit(f"{groupes[eid][0].initiales} : relecture différente de l'attendu, voir {fichier}.")
        print(f"{groupes[eid][0].initiales} : écrit et relu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

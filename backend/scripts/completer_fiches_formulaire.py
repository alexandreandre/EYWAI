"""Complète les fiches salariés dont la valeur juste est connue, sans toucher à la paie.

Lot du 27/10 (écrit) : l'usineur S.B. (Comitech) portait « 9999 », que le
formulaire refuse ; il a reçu 623f, le PCS-ESE de son collègue au même emploi.

Lot du 30/10, pour la DSN d'octobre : la revue pré-paie signale les fiches que
DSN-VAL refuserait (« Fiche à compléter (DSN) »). Les valeurs posées ici se
lisent dans les DSN Quadra de janvier à juillet 2026, sans exception :
- PCS-ESE 674a pour les CDD de production de Colorplast et de Comitech ;
- motif de recours 02 (accroissement temporaire d'activité) pour tous les CDD
  des deux sociétés.
Le PCS se range dans la classification, le motif sous
`specificites_paie.dsn_reprise.motif_recours`, là où le formulaire de la fiche
et la reprise DSN les écrivent. Aucun calcul de bulletin ne lit le PCS ; le
moteur ne lit le motif que pour écarter la prime de précarité, et 02 ne
l'écarte pas (engine/motif_recours.py). Tous les bulletins de ces fiches sont
repris de Quadra (« importe ») : aucun ne passe « À recalculer ».

Restent sans source, donc hors du script : la date de naissance de X.P. et de
F.A. (le NIR ne donne que l'année et le mois), la date de fin et le diplôme
préparé de l'apprenti S.V. de Comitech.

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

#: Les codes que le formulaire propose (`MOTIFS_RECOURS_CDD`, même fichier).
MOTIFS_RECOURS_CDD = frozenset(
    {"01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "12", "13"}
)

#: Les colonnes de la fiche que le script peut corriger.
COLONNES = frozenset({"classification_conventionnelle", "specificites_paie"})

COLORPLAST = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"
COMITECH = "12cd8c71-da13-43f9-9151-475c4d5e8812"


@dataclass(frozen=True)
class Correction:
    employee_id: str
    initiales: str
    societe: str
    #: Colonne de la fiche, et chemin de la clé corrigée dans son JSON.
    colonne: str
    chemin: tuple[str, ...]
    avant: Any
    apres: Any
    source: str


_SOURCE_PCS_COLORPLAST = (
    "PCS-ESE du collègue en CDI au même emploi « Préparateur peintre », et de tous "
    "les CDD de Colorplast déclarés par Quadra (S21.G00.40.004, DSN de mars à juillet 2026)."
)
_SOURCE_PCS_COMITECH = (
    "PCS-ESE des ouvriers de production de Comitech déclarés par Quadra (opérateurs "
    "polyvalents, S21.G00.40.004, DSN de janvier à juillet 2026) ; le seul autre agent "
    "de production, parti le 24/07, portait « 9999 », que le formulaire refuse."
)
_SOURCE_MOTIF = (
    "Motif de tous les CDD déclarés par Quadra chez Colorplast et Comitech "
    "(S21.G00.40.021 = 02, DSN de janvier à juillet 2026, sans exception)."
)


def _pcs(employee_id: str, initiales: str, societe: str, source: str) -> Correction:
    return Correction(employee_id, initiales, societe, "classification_conventionnelle",
                      ("pcs",), None, "674a", source)


def _motif(employee_id: str, initiales: str, societe: str) -> Correction:
    return Correction(employee_id, initiales, societe, "specificites_paie",
                      ("dsn_reprise", "motif_recours"), None, "02", _SOURCE_MOTIF)


CORRECTIONS: tuple[Correction, ...] = (
    _pcs("2e3c07ed-5090-45d6-bbe2-b74b2b7cc36f", "A.B.", COLORPLAST, _SOURCE_PCS_COLORPLAST),
    _motif("2e3c07ed-5090-45d6-bbe2-b74b2b7cc36f", "A.B.", COLORPLAST),
    _pcs("d9133249-b420-4b7a-81ef-015fc0e7dc71", "X.P.", COLORPLAST, _SOURCE_PCS_COLORPLAST),
    _motif("d9133249-b420-4b7a-81ef-015fc0e7dc71", "X.P.", COLORPLAST),
    _pcs("bc90c7bd-b545-4816-965d-a821fb4fc514", "F.A.", COLORPLAST, _SOURCE_PCS_COLORPLAST),
    _motif("bc90c7bd-b545-4816-965d-a821fb4fc514", "F.A.", COLORPLAST),
    _pcs("01ea5d95-fda3-46b7-9e22-280bdf7598ca", "D.G.", COMITECH, _SOURCE_PCS_COMITECH),
    _motif("01ea5d95-fda3-46b7-9e22-280bdf7598ca", "D.G.", COMITECH),
    _motif("b5bb1c56-50b8-4b69-bb2a-01e7e8332682", "V.L.", COMITECH),
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


def _valider(c: Correction) -> None:
    if c.colonne not in COLONNES:
        raise SystemExit(f"{c.initiales} : colonne {c.colonne} hors du formulaire de la fiche, rien n'est écrit.")
    if c.chemin == ("pcs",) and not FORMAT_PCS_ESE.match(str(c.apres)):
        raise SystemExit(f"{c.initiales} : PCS {c.apres!r} refusé par le formulaire, rien n'est écrit.")
    if c.chemin[-1:] == ("motif_recours",) and c.apres not in MOTIFS_RECOURS_CDD:
        raise SystemExit(f"{c.initiales} : motif {c.apres!r} hors de la liste DSN, rien n'est écrit.")


def _lire(valeur: Any, chemin: tuple[str, ...]) -> Any:
    for cle in chemin:
        if not isinstance(valeur, dict):
            return None
        valeur = valeur.get(cle)
    return valeur


def _feuilles(valeur: Any, prefixe: tuple[str, ...] = ()) -> dict[tuple[str, ...], Any]:
    """Chaque valeur du JSON qui n'est pas un objet, avec son chemin."""
    if not isinstance(valeur, dict):
        return {prefixe: valeur}
    feuilles: dict[tuple[str, ...], Any] = {}
    for cle, sous in valeur.items():
        feuilles.update(_feuilles(sous, prefixe + (cle,)))
    return feuilles


def colonnes_corrigees(fiche: dict[str, Any], corrections: list[Correction]) -> dict[str, Any]:
    """Les colonnes de la fiche, seules les clés corrigées changées.

    Arrête tout si une valeur d'avant n'est pas celle attendue, si une valeur
    corrigée ne passe pas le formulaire, ou si une autre clé changerait.
    """
    nouvelles: dict[str, Any] = {}
    for c in corrections:
        _valider(c)
        origine = fiche.get(c.colonne)
        if origine is not None and not isinstance(origine, dict):
            raise SystemExit(f"{c.initiales} : {c.colonne} n'est pas un objet, rien n'est écrit.")
        if _lire(origine, c.chemin) != c.avant:
            raise SystemExit(
                f"{c.initiales} : {c.colonne}.{'.'.join(c.chemin)} vaut {_lire(origine, c.chemin)!r}, "
                f"{c.avant!r} attendu — la fiche a changé, rien n'est écrit."
            )
        noeud = nouvelles.setdefault(c.colonne, copy.deepcopy(origine or {}))
        for cle in c.chemin[:-1]:
            noeud = noeud.setdefault(cle, {})
            if not isinstance(noeud, dict):
                raise SystemExit(f"{c.initiales} : {c.colonne}.{cle} n'est pas un objet, rien n'est écrit.")
        noeud[c.chemin[-1]] = c.apres
    for colonne, nouvelle in nouvelles.items():
        avant, apres = _feuilles(fiche.get(colonne) or {}), _feuilles(nouvelle)
        changees = {p for p in set(avant) | set(apres) if avant.get(p) != apres.get(p)}
        attendues = {c.chemin for c in corrections if c.colonne == colonne}
        if changees != attendues:
            raise SystemExit(f"Clés changées {sorted(changees)} au lieu de {sorted(attendues)} : rien n'est écrit.")
    return nouvelles


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
        plan[eid] = colonnes_corrigees(fiche, corrections)
        calcules = [b for b in etats[eid]["bulletins"] if (b.get("origine") or "calcule") != "importe"]
        for c in corrections:
            print(f"{c.initiales} {c.colonne}.{'.'.join(c.chemin)} : {c.avant!r} -> {c.apres!r}")
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

    for eid, colonnes in plan.items():
        fiche = fiches[eid]
        initiales = groupes[eid][0].initiales
        reponse = (
            supabase.table("employees")
            .update(colonnes)
            .eq("id", eid)
            .eq("updated_at", fiche["updated_at"])
            .execute()
        )
        if len(reponse.data or []) != 1:
            raise SystemExit(f"{initiales} : fiche modifiée entre la lecture et l'écriture, arrêt.")
        relue = lire_fiche(eid)
        ignorees = set(colonnes) | {"updated_at"}
        attendu = {k: v for k, v in fiche.items() if k not in ignorees}
        obtenu = {k: v for k, v in relue.items() if k not in ignorees}
        if any(relue.get(k) != v for k, v in colonnes.items()) or attendu != obtenu:
            raise SystemExit(f"{initiales} : relecture différente de l'attendu, voir {fichier}.")
        print(f"{initiales} : écrit et relu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

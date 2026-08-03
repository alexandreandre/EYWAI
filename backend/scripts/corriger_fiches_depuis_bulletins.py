"""Corrige les fiches salariés à partir des bulletins de paie réels.

Le bulletin porte des mentions contractuelles opposables — civilité, forfait
annuel en jours, emploi, coefficient — que notre base contredit parfois. Ce
script les relève, les compare, et ne corrige que ce qui est prouvé par le
bulletin. Aucun nom n'est écrit ici : les cibles sortent des fichiers.

Le sexe se recoupe en plus avec le NIR, dont la clé de contrôle est vérifiée :
quand la civilité du bulletin et le NIR disent la même chose, la fiche a tort.

Usage :
    python scripts/corriger_fiches_depuis_bulletins.py --societe lewis --mois 2026-05
    python scripts/corriger_fiches_depuis_bulletins.py --societe lewis --mois 2026-05 --apply
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.shared.dsn_validation import validate_nir  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]

SOCIETES = {
    "cartol": "Cartol Industrie",
    "colorplast": "Colorplast",
    "comitech": "Comitech Composite",
    "lewis": "LEWIS",
    "maji": "MAJI",
    "mbc": "Mont Blanc Composite",
    "zone": "Zone 404 Mars",
}

RE_NIR = re.compile(r"NoS[eé]cu\.?\s*:\s*([0-9 ]{13,20})")
RE_CIVILITE = re.compile(r"^\s*(M\.|MME|Mme|MLLE)\s+\S")
RE_FORFAIT = re.compile(r"Forfait annuel\s*:\s*([\d.,]+)\s*jours", re.IGNORECASE)
RE_EMPLOI = re.compile(r"Emploi\s*:\s*(.+?)\s{2,}(?:Ancienneté|$)")
RE_COEFF = re.compile(r"Coeff\s*:\s*(\S+)")


@dataclass
class Releve:
    """Ce que le bulletin dit d'un salarié."""

    nir: str
    civilite: str = ""
    forfait_jours: Optional[float] = None
    emploi: str = ""
    coefficient: str = ""


def lire_bulletins(societe: str, mois: str) -> Dict[str, Releve]:
    dossier = RACINE / "data" / societe / "bulletins" / mois
    if not dossier.exists():
        raise SystemExit(f"Aucun bulletin sous {dossier}")
    releves: Dict[str, Releve] = {}
    for pdf in sorted(dossier.glob("*.pdf")):
        texte = subprocess.run(
            ["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True
        ).stdout
        lignes = texte.splitlines()
        for index, ligne in enumerate(lignes):
            trouve = RE_NIR.search(ligne)
            if not trouve:
                continue
            nir = re.sub(r"\D", "", trouve.group(1))[:13]
            releve = releves.setdefault(nir, Releve(nir=nir))
            # La civilité précède le matricule dans le cartouche.
            for precedente in reversed(lignes[max(0, index - 14) : index]):
                if RE_CIVILITE.match(precedente):
                    releve.civilite = precedente.split()[0].upper().rstrip(".")
                    break
            # L'emploi et le forfait suivent le matricule.
            for suivante in lignes[index : index + 8]:
                forfait = RE_FORFAIT.search(suivante)
                if forfait:
                    releve.forfait_jours = float(forfait.group(1).replace(",", "."))
                emploi = RE_EMPLOI.search(suivante)
                if emploi and not releve.emploi:
                    releve.emploi = emploi.group(1).strip()
                coeff = RE_COEFF.search(suivante)
                if coeff and not releve.coefficient:
                    releve.coefficient = coeff.group(1).strip()
    return releves


def charger_salaries(nom_societe: str) -> Dict[str, dict]:
    reponse = (
        supabase.table("companies").select("id").eq("company_name", nom_societe).execute()
    )
    lignes = reponse.data or []
    if not lignes:
        raise SystemExit(f"Société introuvable : {nom_societe}")
    salaries = (
        supabase.table("employees")
        .select(
            "id, first_name, last_name, nir, sexe, is_forfait_jour, job_title, "
            "classification_conventionnelle"
        )
        .eq("company_id", lignes[0]["id"])
        .execute()
    ).data or []
    return {re.sub(r"\D", "", str(e.get("nir") or ""))[:13]: e for e in salaries}


@dataclass
class Correction:
    employee_id: str
    libelle: str
    champ: str
    avant: object
    apres: object
    preuve: str
    patch: dict = field(default_factory=dict)


def comparer(releves: Dict[str, Releve], salaries: Dict[str, dict]) -> List[Correction]:
    corrections: List[Correction] = []
    for nir, releve in sorted(releves.items()):
        salarie = salaries.get(nir)
        if not salarie:
            continue
        qui = f"{salarie['last_name']} {salarie['first_name']}"

        # Sexe : le bulletin et le NIR doivent dire la même chose que la fiche.
        attendu_nir = "M" if nir[:1] == "1" else "F" if nir[:1] == "2" else ""
        attendu_bulletin = (
            "M" if releve.civilite == "M" else "F" if releve.civilite in {"MME", "MLLE"} else ""
        )
        cle_valide, _ = validate_nir(str(salarie.get("nir") or ""))
        if (
            attendu_nir
            and attendu_nir == attendu_bulletin
            and salarie.get("sexe") != attendu_nir
            and cle_valide
        ):
            corrections.append(
                Correction(
                    salarie["id"],
                    qui,
                    "sexe",
                    salarie.get("sexe"),
                    attendu_nir,
                    f"civilité « {releve.civilite} » au bulletin, NIR commençant par {nir[0]}",
                    {"sexe": attendu_nir},
                )
            )

        # Forfait annuel en jours : mention contractuelle du bulletin.
        if releve.forfait_jours and not salarie.get("is_forfait_jour"):
            corrections.append(
                Correction(
                    salarie["id"],
                    qui,
                    "is_forfait_jour",
                    salarie.get("is_forfait_jour"),
                    True,
                    f"« Forfait annuel : {releve.forfait_jours:.2f} jours » au bulletin",
                    {"is_forfait_jour": True},
                )
            )

        # Emploi et coefficient : signalés, jamais corrigés d'office (ils
        # touchent au minimum conventionnel et à la prime d'ancienneté).
        classification = salarie.get("classification_conventionnelle") or {}
        if releve.emploi and classification.get("libelle_emploi") not in (
            releve.emploi,
            None,
        ):
            if str(classification.get("libelle_emploi") or "") != releve.emploi:
                corrections.append(
                    Correction(
                        salarie["id"],
                        qui,
                        "classification.libelle_emploi",
                        classification.get("libelle_emploi"),
                        releve.emploi,
                        "libellé d'emploi du bulletin",
                    )
                )
        # Le bulletin n'imprime parfois que la lettre du niveau (« C » pour
        # « 5 C ») : ce n'est pas une divergence, seulement une troncature.
        notre_niveau = str(classification.get("niveau_dsn") or "")
        tronque = releve.coefficient in notre_niveau.split() or notre_niveau.endswith(
            f" {releve.coefficient}"
        )
        if releve.coefficient and notre_niveau and not tronque:
            corrections.append(
                Correction(
                    salarie["id"],
                    qui,
                    "classification.niveau_dsn",
                    classification.get("niveau_dsn"),
                    releve.coefficient,
                    "coefficient du bulletin",
                )
            )
    return corrections


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--societe", required=True, choices=sorted(SOCIETES))
    parser.add_argument("--mois", required=True, help="AAAA-MM")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="applique les corrections automatiques (sexe, forfait-jours)",
    )
    parser.add_argument(
        "--aligner-classification",
        action="store_true",
        help=(
            "aligne aussi l'emploi et le coefficient sur le bulletin ; le "
            "coefficient commande le minimum conventionnel, à ne faire "
            "qu'après arbitrage"
        ),
    )
    args = parser.parse_args()

    releves = lire_bulletins(args.societe, args.mois)
    salaries = charger_salaries(SOCIETES[args.societe])
    corrections = comparer(releves, salaries)

    if args.aligner_classification:
        # Reconstruit le patch de classification à partir de la fiche courante :
        # c'est un champ JSON, on ne remplace que la clé visée.
        for c in corrections:
            if c.patch or not c.champ.startswith("classification."):
                continue
            cle = c.champ.split(".", 1)[1]
            fiche = next(
                (e for e in salaries.values() if e["id"] == c.employee_id), None
            )
            if fiche is None:
                continue
            classification = dict(fiche.get("classification_conventionnelle") or {})
            classification[cle] = c.apres
            c.patch = {"classification_conventionnelle": classification}

    automatiques = [c for c in corrections if c.patch]
    a_arbitrer = [c for c in corrections if not c.patch]

    print(
        f"{args.societe} {args.mois} : {len(releves)} bulletins lus, "
        f"{len(salaries)} fiches en base"
    )
    print(f"\nCorrections prouvées par le bulletin ({len(automatiques)}) :")
    for c in automatiques:
        print(f"  {c.libelle:32s} {c.champ:16s} {c.avant!r} → {c.apres!r}  [{c.preuve}]")
    print(f"\nÀ arbitrer, non corrigé ({len(a_arbitrer)}) :")
    for c in a_arbitrer:
        print(f"  {c.libelle:32s} {c.champ:28s} {c.avant!r} → {c.apres!r}")

    if not args.apply:
        print("\nAucune écriture (ajouter --apply pour les corrections prouvées).")
        return 0

    for c in automatiques:
        supabase.table("employees").update(c.patch).eq("id", c.employee_id).execute()
    print(f"\n{len(automatiques)} fiche(s) corrigée(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

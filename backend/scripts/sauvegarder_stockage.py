"""
Sauvegarde locale des fichiers du stockage (LECTURE SEULE côté serveur).

Le stockage Supabase n'est couvert par AUCUNE sauvegarde : la base a ses
instantanés quotidiens, les fichiers non. Or il contient les documents qui
ne se régénèrent pas — 1384 bulletins de paie, les contrats de travail, les
soldes de tout compte, les attestations. Leur perte serait définitive.

    python -m scripts.sauvegarder_stockage                 # tout
    python -m scripts.sauvegarder_stockage --prioritaires  # documents légaux
    python -m scripts.sauvegarder_stockage --bucket payslips

Reprend où elle s'est arrêtée : un fichier déjà présent avec la même taille
n'est pas retéléchargé. Destination : `data/_sauvegardes/stockage/`,
gitignoré — ces fichiers sont nominatifs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

from app.core.database import supabase

RACINE = Path(__file__).resolve().parents[2] / "data" / "_sauvegardes" / "stockage"

#: Documents qui n'existent qu'ici et n'ont aucune source de reconstitution.
BUCKETS_PRIORITAIRES = (
    "payslips",
    "contracts",
    "exit_documents",
    "salary_certificates",
    "advance_payments",
    "employee_loan_contracts",
    "piece_identite",
)

TAILLE_PAGE = 100


def _lister_objets(bucket: str, prefixe: str = "") -> List[Dict]:
    """Tous les objets d'un bucket, dossiers parcourus récursivement."""
    trouves: List[Dict] = []
    decalage = 0
    while True:
        try:
            lot = supabase.storage.from_(bucket).list(
                prefixe, {"limit": TAILLE_PAGE, "offset": decalage}
            )
        except Exception as exc:
            print(f"    lecture impossible ({prefixe or '/'}) : {str(exc)[:70]}")
            return trouves
        if not lot:
            return trouves
        for entree in lot:
            nom = entree.get("name")
            if not nom:
                continue
            chemin = f"{prefixe}/{nom}" if prefixe else nom
            # Un « dossier » n'a pas de métadonnées de fichier.
            if entree.get("id") is None and not entree.get("metadata"):
                trouves.extend(_lister_objets(bucket, chemin))
            else:
                trouves.append(
                    {"chemin": chemin, "taille": (entree.get("metadata") or {}).get("size", 0)}
                )
        if len(lot) < TAILLE_PAGE:
            return trouves
        decalage += TAILLE_PAGE


def sauvegarder_bucket(bucket: str) -> Dict[str, int]:
    objets = _lister_objets(bucket)
    bilan = {"total": len(objets), "copies": 0, "deja": 0, "echecs": 0, "octets": 0}
    for objet in objets:
        cible = RACINE / bucket / objet["chemin"]
        taille_attendue = int(objet["taille"] or 0)
        if cible.exists() and (taille_attendue == 0 or cible.stat().st_size == taille_attendue):
            bilan["deja"] += 1
            continue
        try:
            contenu = supabase.storage.from_(bucket).download(objet["chemin"])
        except Exception as exc:
            bilan["echecs"] += 1
            print(f"    échec : {objet['chemin'][:60]} ({str(exc)[:50]})")
            continue
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(contenu)
        bilan["copies"] += 1
        bilan["octets"] += len(contenu)
    return bilan


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--bucket", help="un seul bucket")
    parseur.add_argument(
        "--prioritaires",
        action="store_true",
        help="uniquement les documents légaux irremplaçables",
    )
    options = parseur.parse_args()

    if options.bucket:
        buckets = [options.bucket]
    else:
        try:
            tous = [b.name for b in supabase.storage.list_buckets()]
        except Exception as exc:
            print(f"Impossible de lister les buckets : {exc}")
            return 2
        buckets = (
            [b for b in BUCKETS_PRIORITAIRES if b in tous]
            if options.prioritaires
            else tous
        )

    print(f"\nSauvegarde du stockage → {RACINE}\n" + "=" * 62)
    total = {"copies": 0, "deja": 0, "echecs": 0, "octets": 0}
    for bucket in buckets:
        print(f"\n{bucket}")
        bilan = sauvegarder_bucket(bucket)
        for cle in total:
            total[cle] += bilan[cle]
        print(
            f"   {bilan['total']:>5} objets | {bilan['copies']:>5} copiés | "
            f"{bilan['deja']:>5} déjà présents | {bilan['echecs']} échecs"
        )

    mo = total["octets"] / (1024 * 1024)
    print(
        f"\n{'=' * 62}\nTOTAL : {total['copies']} copiés ({mo:.1f} Mo), "
        f"{total['deja']} déjà présents, {total['echecs']} échecs\n"
    )
    return 1 if total["echecs"] else 0


if __name__ == "__main__":
    sys.exit(main())

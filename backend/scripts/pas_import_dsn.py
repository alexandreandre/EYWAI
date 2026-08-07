"""Reprend les taux de prélèvement à la source depuis les DSN d'un mois.

L'écran `/taux-pas` fait déjà ce travail société par société, fichier par fichier.
Ce script est le même chemin — `preparer_apercu()` puis `appliquer()` — appliqué
d'un coup aux sept sociétés à partir des DSN rangées sous `data/<societe>/dsn/`,
pour les mois que le cabinet dépose en lot.

L'opération est rejouable : l'unicité `(employee_id, periode, source)` sur
`employee_pas_rates` empêche le doublon, et un taux inchangé n'écrit rien.

Rappel utile en lisant l'aperçu : un taux de type barème (13, 23, 33, 17, 27, 37)
est recalculé à chaque paie par le moteur ; sa valeur en base ne sert qu'à montrer
aux RH ce que le cabinet a déclaré. Seul le type 01 pilote un bulletin.

Usage :
    python scripts/pas_import_dsn.py --periode 2026-06              # aperçu seul
    python scripts/pas_import_dsn.py --periode 2026-06 --apply      # écrit en base
    python scripts/pas_import_dsn.py --periode 2026-06 --societe mbc
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import get_supabase_admin_client  # noqa: E402
from app.modules.pas_rates.application import ingest  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]

_NOMS_SOCIETE = ("name", "nom", "raison_sociale", "company_name", "libelle")


def nom_societe(societe: Dict[str, Any]) -> str:
    for cle in _NOMS_SOCIETE:
        if societe.get(cle):
            return str(societe[cle])
    return str(societe.get("id"))


def siren_du_fichier(contenu: bytes) -> str:
    """Le SIREN déclaré, seule clé fiable pour relier un fichier à une société."""
    for ligne in contenu.decode("latin-1", "replace").splitlines():
        if ligne.startswith("S21.G00.06.001"):
            return ligne.split(",", 1)[1].strip().strip("'")
    return ""


def fichiers_du_mois(periode: str, societe: Optional[str]) -> List[Path]:
    motif = f"{societe or '*'}/dsn/{periode}.dsn"
    return sorted((RACINE / "data").glob(motif))


def decrire(ligne: Any) -> str:
    if ligne.nature == "modifie":
        return (
            f"    modifié   {ligne.nom} {ligne.prenom} : "
            f"{ligne.taux_actuel} % ({ligne.type_actuel}) "
            f"-> {ligne.taux_fichier} % ({ligne.type_fichier})"
        )
    if ligne.nature == "nouveau":
        return (
            f"    nouveau   {ligne.nom} {ligne.prenom} : "
            f"{ligne.taux_fichier} % ({ligne.type_fichier})"
        )
    return f"    inconnu   {ligne.nom} {ligne.prenom} — absent du SIRH, ignoré"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--periode", required=True, help="AAAA-MM du mois déclaré")
    parser.add_argument("--societe", help="dossier sous data/, toutes par défaut")
    parser.add_argument(
        "--apply", action="store_true", help="écrit en base (aperçu seul sans ce drapeau)"
    )
    args = parser.parse_args()

    fichiers = fichiers_du_mois(args.periode, args.societe)
    if not fichiers:
        print(f"Aucune DSN {args.periode} sous data/. Rien à faire.")
        return 1

    societes = get_supabase_admin_client().table("companies").select("*").execute().data or []
    par_siren = {str(c.get("siren") or "").strip(): c for c in societes}

    total = {"modifie": 0, "nouveau": 0, "applique": 0, "historique": 0, "echec": 0}
    for chemin in fichiers:
        dossier = chemin.parts[-3]
        contenu = chemin.read_bytes()
        societe = par_siren.get(siren_du_fichier(contenu))
        if not societe:
            print(f"{dossier} : SIREN {siren_du_fichier(contenu)} inconnu en base, ignoré")
            continue

        try:
            apercu = ingest.preparer_apercu(
                company_id=str(societe["id"]),
                content=contenu,
                file_name=chemin.name,
                source="dsn",
            )
        except ingest.FichierInvalide as exc:
            print(f"{dossier} : {exc}")
            total["echec"] += 1
            continue

        compteurs = apercu.compteurs()
        total["modifie"] += compteurs["modifie"]
        total["nouveau"] += compteurs["nouveau"]
        print(f"\n{nom_societe(societe)} — {chemin.name} — période {apercu.periode}")
        print(f"    {compteurs}")
        for ligne in apercu.lignes:
            if ligne.nature in ("modifie", "nouveau", "non_rapproche"):
                print(decrire(ligne))
        for avertissement in apercu.avertissements:
            print(f"    ! {avertissement}")

        if not args.apply:
            continue
        resultat = ingest.appliquer(str(societe["id"]), apercu)
        total["applique"] += resultat["appliques"]
        total["historique"] += resultat["historique"]
        total["echec"] += len(resultat["echecs"])
        for echec in resultat["echecs"]:
            print(f"    ÉCHEC {echec['salarie']} : {echec['erreur']}")

    print(f"\n{'APPLIQUÉ' if args.apply else 'APERÇU'} — {total}")
    if not args.apply:
        print("Relancer avec --apply pour écrire.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Reprend le paramétrage DSN depuis la dernière DSN déposée par le cabinet.

Émetteur, contacts, NAF déclaré et IDCC ne se déduisent d'aucun bulletin. Plutôt
que de les ressaisir, on les lit dans le dernier fichier du cabinet, qui a été
accepté par net-entreprises, puis on les rend modifiables.

Usage :
    python scripts/dsn_settings_reprise.py --dry-run        # montre sans écrire
    python scripts/dsn_settings_reprise.py --apply          # écrit en base
    python scripts/dsn_settings_reprise.py --fichier        # écrit hors base
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.dsn_export.domain.settings import (  # noqa: E402
    DsnSettings,
    extraire_depuis_dsn,
    vers_dict,
)

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


def derniere_dsn(dossier: str) -> Optional[Path]:
    repertoire = RACINE / "data" / dossier / "dsn"
    fichiers = sorted(repertoire.glob("*.dsn")) if repertoire.exists() else []
    return fichiers[-1] if fichiers else None


def decrire(settings: DsnSettings) -> str:
    contacts = ", ".join(
        c.code_destinataire for c in settings.contacts_declaration
    )
    return (
        f"émetteur {settings.emetteur_siren} {settings.emetteur_raison_sociale} | "
        f"contact {settings.contact_emetteur_nom} | NAF {settings.naf} | "
        f"IDCC {settings.idcc} | destinataires {contacts or 'aucun'}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--societe", choices=sorted(SOCIETES))
    groupe = parser.add_mutually_exclusive_group()
    groupe.add_argument("--apply", action="store_true", help="écrit en base")
    groupe.add_argument(
        "--fichier",
        action="store_true",
        help="écrit sous data/_dsn_conformance/<societe>/settings.json",
    )
    args = parser.parse_args()

    dossiers = [args.societe] if args.societe else sorted(SOCIETES)
    ecrits = 0
    for dossier in dossiers:
        source = derniere_dsn(dossier)
        if not source:
            print(f"{dossier:11s} : aucune DSN cabinet disponible")
            continue
        settings = extraire_depuis_dsn(source.read_bytes(), fichier=source.name)
        manques = settings.manques()
        etat = "complet" if not manques else f"incomplet ({', '.join(manques)})"
        print(f"{dossier:11s} : {decrire(settings)}")
        print(f"{'':11s}   source {source.name}, {etat}")

        if args.fichier:
            cible = RACINE / "data" / "_dsn_conformance" / dossier
            cible.mkdir(parents=True, exist_ok=True)
            (cible / "settings.json").write_text(
                json.dumps(vers_dict(settings), ensure_ascii=False, indent=1)
            )
            ecrits += 1
        elif args.apply:
            from app.modules.dsn_export.infrastructure import settings_repository

            from app.core.database import supabase

            reponse = (
                supabase.table("companies")
                .select("id")
                .eq("company_name", SOCIETES[dossier])
                .execute()
            )
            lignes = reponse.data or []
            if not lignes:
                print(f"{'':11s}   société introuvable en base, ignorée")
                continue
            settings_repository.enregistrer(lignes[0]["id"], settings)
            ecrits += 1

    if not args.apply and not args.fichier:
        print("\nAucune écriture (ajouter --apply ou --fichier).")
    else:
        print(f"\n{ecrits} paramétrage(s) écrit(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Rapatrie le texte de base intégral des conventions collectives (colonne base_text).

`full_text` est le corpus paie : avenants salaires, annexes, extrait rémunération.
Il ne contient ni période d'essai, ni préavis, ni congés — ce dont l'assistant RH
a besoin. Ce script remplit `base_text` pour les conventions déjà en catalogue,
**sans toucher à `full_text`**, donc sans risque pour le moteur de paie.

La synchronisation mensuelle KALI alimente désormais les deux colonnes ; ce script
sert au rattrapage initial et au dépannage ciblé.

Usage :
    venv/bin/python scripts/backfill_cc_base_text.py              # simulation
    venv/bin/python scripts/backfill_cc_base_text.py --apply
    venv/bin/python scripts/backfill_cc_base_text.py --idcc 0292 --apply
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Repères utilisés pour vérifier qu'on a bien récupéré une convention et non un
# recueil d'avenants salariaux (le symptôme exact du corpus paie).
REPERES = ("essai", "préavis", "congé", "ancienneté", "licenciement")


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--idcc", default="", help="ne traiter qu'un IDCC")
    parseur.add_argument(
        "--apply", action="store_true", help="écrit en base (sinon simulation)"
    )
    args = parseur.parse_args()

    from app.core.database import get_supabase_client
    from app.modules.collective_agreements.infrastructure.kali_client import KaliClient
    from app.modules.collective_agreements.infrastructure.providers import (
        AgreementTextCacheProvider,
    )

    supabase = get_supabase_client()
    client = KaliClient()
    client.require_configured()
    cache = AgreementTextCacheProvider(supabase)

    requete = (
        supabase.table("collective_agreements_catalog")
        .select("id, idcc, name")
        .eq("is_active", True)
    )
    if args.idcc:
        requete = requete.eq("idcc", args.idcc)
    conventions = requete.execute().data or []
    if not conventions:
        print("Aucune convention active à traiter.")
        return 1

    print(f"{len(conventions)} convention(s) — mode "
          f"{'ÉCRITURE' if args.apply else 'simulation'}\n")
    echecs = 0

    for convention in conventions:
        idcc = str(convention.get("idcc") or "").strip()
        nom = str(convention.get("name") or "")[:60]
        print(f"IDCC {idcc} — {nom}")
        try:
            meta = client.resolve_convention(idcc)
            conteneur = client._post("consult/kaliCont", {"id": meta.kalicont_id})
            sections = ((conteneur or {}).get("conteneur") or conteneur or {}).get(
                "sections"
            ) or []
            base_text, articles, _ = client._collect_base_text(sections)
        except Exception as exc:  # noqa: BLE001 - on continue sur les suivantes
            print(f"  ÉCHEC : {type(exc).__name__} — {exc}\n")
            echecs += 1
            continue

        if not base_text.strip():
            print("  ÉCHEC : aucun texte de base en vigueur trouvé\n")
            echecs += 1
            continue

        trouves = {
            mot: len(re.findall(mot, base_text, re.I)) for mot in REPERES
        }
        print(f"  {len(base_text)} caractères, {articles} article(s) rapatrié(s)")
        print("  " + "  ".join(f"{m}={n}" for m, n in trouves.items()))
        if not any(trouves.values()):
            print("  ATTENTION : aucun repère RH trouvé, texte suspect — non écrit\n")
            echecs += 1
            continue

        if args.apply:
            cache.set_base_text(convention["id"], base_text)
            print("  écrit dans base_text\n")
        else:
            print("  (simulation, rien écrit)\n")

    if echecs:
        print(f"{echecs} convention(s) en échec.")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())

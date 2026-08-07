"""Extraction puis classement de la conversation WhatsApp, en une commande.

    python -m scripts.data_organize.actualiser              # simulation
    python -m scripts.data_organize.actualiser --appliquer  # range sous data/

L'extraction a lieu dans les deux cas : elle est sans effet de bord hors de
`data/_inbox/`, et il faut bien lire le fil pour savoir ce qui a changé. Seul
le rangement sous `data/<societe>/…` est conditionné par `--appliquer`.
"""

from __future__ import annotations

import argparse
import sys

from scripts.data_organize import extraire_whatsapp, ingerer


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--contact", default="Elsa", help="nom du contact WhatsApp")
    analyseur.add_argument("--appliquer", action="store_true", help="range les nouveautés")
    arguments = analyseur.parse_args(argv)

    dossier, rapport = extraire_whatsapp.extraire(arguments.contact)
    print(f"=== conversation {arguments.contact} ===")
    print(
        f"{rapport.messages} messages, {rapport.pieces_copiees} pièces récupérées, "
        f"{rapport.pieces_absentes} restées sur le téléphone"
    )

    pieces = ingerer.analyser(dossier)
    ingerer.afficher(pieces)

    if arguments.appliquer:
        copiees = ingerer.appliquer(pieces)
        print(f"\n{copiees} fichiers rangés sous data/")
    else:
        a_ranger = sum(1 for piece in pieces if piece.etat == ingerer.NOUVEAU)
        print(f"\nSimulation. {a_ranger} fichiers à ranger : relancer avec --appliquer.")

    if rapport.nouveaux:
        chemin = dossier / extraire_whatsapp.FICHIER_NOUVEAUTES
        print(f"\n{len(rapport.nouveaux)} messages nouveaux depuis la dernière fois : {chemin}")
        print("Les lire : ils portent ce qu'aucune pièce jointe ne dit.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

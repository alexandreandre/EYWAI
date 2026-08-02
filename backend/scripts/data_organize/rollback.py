"""Annulation d'une migration de données.

Rejoue `data/_manifeste.json` à l'envers : retire le lien symbolique laissé à
l'ancien emplacement, puis y ramène le fichier. Ne supprime jamais de contenu.

    python -m scripts.data_organize.rollback              # simulation
    python -m scripts.data_organize.rollback --appliquer  # exécution
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.data_organize.inventaire import RACINE_DATA, RACINE_DEPOT
from scripts.data_organize.migrer import MANIFESTE


def charger() -> dict:
    if not MANIFESTE.exists():
        raise SystemExit(f"Aucun manifeste à annuler : {MANIFESTE}")
    return json.loads(MANIFESTE.read_text(encoding="utf-8"))


def annuler(manifeste: dict, appliquer: bool) -> tuple[int, list[str]]:
    restaures = 0
    anomalies: list[str] = []

    # Ordre inverse : un fichier archivé après coup retrouve sa place avant que
    # le gagnant ne libère la sienne.
    for mouvement in reversed(manifeste["mouvements"]):
        source = RACINE_DEPOT / mouvement["source"]
        cible = RACINE_DATA / mouvement["cible"]

        if not cible.exists():
            anomalies.append(f"introuvable, ignoré : data/{mouvement['cible']}")
            continue

        if not appliquer:
            restaures += 1
            continue

        if source.is_symlink():
            source.unlink()
        elif source.exists():
            anomalies.append(f"occupé par un vrai fichier, ignoré : {mouvement['source']}")
            continue

        source.parent.mkdir(parents=True, exist_ok=True)
        cible.rename(source)
        restaures += 1

    return restaures, anomalies


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--appliquer", action="store_true")
    arguments = analyseur.parse_args(argv)

    manifeste = charger()
    print(f"Manifeste du {manifeste['genere_le']} : {len(manifeste['mouvements'])} mouvements")

    restaures, anomalies = annuler(manifeste, arguments.appliquer)
    verbe = "restaurés" if arguments.appliquer else "restaurables"
    print(f"{restaures} fichiers {verbe}")

    for anomalie in anomalies[:20]:
        print(f"  ! {anomalie}")
    if len(anomalies) > 20:
        print(f"  ... et {len(anomalies) - 20} autres")

    if not arguments.appliquer:
        print("\nSimulation. Ajouter --appliquer pour exécuter.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

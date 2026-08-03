"""Chargement des tables nominatives depuis `data/` (hors dépôt Git).

Les tables associant un salarié réel à ses montants (participation, heures RCR,
planning) sont des données à caractère personnel : elles n'ont rien à faire dans
le code versionné. Elles vivent sous `data/<societe>/referentiel/`, gitignoré.

Un script qui en a besoin appelle `charger()`. Si le fichier est absent, l'erreur
est explicite plutôt que silencieuse.
"""

from __future__ import annotations

import json
from pathlib import Path

RACINE_DATA = Path(__file__).resolve().parents[2] / "data"


def chemin_table(societe: str, nom: str) -> Path:
    return RACINE_DATA / societe / "referentiel" / f"{nom}.json"


def charger(societe: str, nom: str) -> list[dict]:
    """Lit `data/<societe>/referentiel/<nom>.json`.

    Lève `FileNotFoundError` avec un message actionnable si la table manque —
    typiquement sur une machine qui n'a pas les données client.
    """
    chemin = chemin_table(societe, nom)
    if not chemin.is_file():
        raise FileNotFoundError(
            f"Table nominative absente : {chemin}\n"
            f"Ces données sont personnelles et ne sont pas versionnées. "
            f"Voir docs/donnees-locales.md."
        )
    return json.loads(chemin.read_text(encoding="utf-8"))


def charger_ou_vide(societe: str, nom: str) -> list[dict]:
    """Comme `charger`, mais renvoie une liste vide si la table manque.

    À utiliser quand l'absence de données doit dégrader le comportement sans
    faire échouer l'import du module (collecte des tests, par exemple).
    """
    try:
        return charger(societe, nom)
    except FileNotFoundError:
        return []

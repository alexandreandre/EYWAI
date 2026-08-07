"""Gel des tests d'intégration en échec connu.

Le job « Backend integration » tournait en `continue-on-error` : son rouge ne
coûtait rien, donc personne ne le regardait, et 73 tests ont dérivé du code sans
que ça se voie. Les remettre au vert d'un coup demanderait de reprendre 21
fichiers ; en attendant, on les déclare en échec attendu pour que le job puisse
redevenir bloquant et que la prochaine régression, elle, se voie.

`strict=True` est délibéré : un test de la liste qui se remet à passer fait
échouer la CI, ce qui force à retirer sa ligne. La liste ne peut donc que
maigrir — jamais dormir.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Set

import pytest

_LISTE = Path(__file__).parent / "known_failures.txt"


def _echecs_connus() -> Set[str]:
    if not _LISTE.exists():
        return set()
    lignes = _LISTE.read_text("utf-8").splitlines()
    return {
        ligne.strip()
        for ligne in lignes
        if ligne.strip() and not ligne.lstrip().startswith("#")
    }


def pytest_collection_modifyitems(config: pytest.Config, items: List[pytest.Item]) -> None:
    connus = _echecs_connus()
    if not connus:
        return
    for item in items:
        # `nodeid` est déjà relatif à la racine pytest et sépare la classe du test
        # par `::` — exactement la forme que produit la sortie `FAILED …`, donc
        # celle que contient le fichier.
        if item.nodeid in connus:
            item.add_marker(
                pytest.mark.xfail(
                    reason=(
                        "Échec connu, gelé dans tests/integration/known_failures.txt. "
                        "S'il passe désormais, retirer sa ligne du fichier."
                    ),
                    strict=True,
                )
            )

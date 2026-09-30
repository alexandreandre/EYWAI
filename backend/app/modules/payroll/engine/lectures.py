"""Les lectures sans lesquelles un bulletin serait faux : relues, puis bloquantes.

Une lecture en base qui échoue pendant le calcul (délai réseau, coupure) ne doit
jamais produire un bulletin amputé avec un simple avertissement. Revue du
29/09/2026 : une coupure d'une minute a fait perdre sa prime d'ancienneté
(461,97 €) à un salarié de Comitech, parce que les règles de la convention
n'avaient pas été lues ; rien ne se voyait sur le bulletin imprimé.

`lire_ou_arreter` relit deux fois sur une erreur réseau passagère, puis lève
`LectureIndispensable` avec une phrase qui dit quoi faire. Une réponse vide
n'est pas un échec : une convention sans prime d'ancienneté, ou un salarié sans
évolution de salaire, se calculent normalement.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from app.core.logging import get_logger
from app.core.supabase_resilience import is_transient_supabase_error

logger = get_logger(__name__)

T = TypeVar("T")

#: Relectures après un premier échec, et pause entre deux essais (secondes).
RELECTURES = 2
PAUSE = 1.0


class LectureIndispensable(RuntimeError):
    """Une donnée du bulletin n'a pas pu être lue : le bulletin n'est pas calculé."""


def lire_ou_arreter(lire: Callable[[], T], quoi: str) -> T:
    """Le résultat de `lire()`, relu sur erreur réseau passagère ; sinon une erreur claire.

    `quoi` ouvre la phrase affichée, par exemple « Les règles de la convention
    collective n'ont pas pu être lues ».
    """
    derniere: Exception | None = None
    for essai in range(RELECTURES + 1):
        try:
            return lire()
        except Exception as exc:  # noqa: BLE001 — toute lecture ratée arrête le calcul
            derniere = exc
            logger.warning("%s : lecture ratée, essai %s sur %s : %s",
                           quoi, essai + 1, RELECTURES + 1, exc)
            if not is_transient_supabase_error(exc) or essai == RELECTURES:
                break
            time.sleep(PAUSE * (essai + 1))
    raise LectureIndispensable(
        f"{quoi} (connexion à la base interrompue). "
        "Le bulletin n'a pas été calculé : réessayez dans un instant."
    ) from derniere

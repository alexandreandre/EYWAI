"""
Journal des échanges avec l'assistant RH.

Sert à savoir ce qui est réellement demandé — et ce qui échoue — plutôt que de
l'améliorer d'après un banc d'essai reconstitué.

Deux règles de conception :
- le journal ne doit JAMAIS empêcher une réponse : toute erreur d'écriture est
  avalée après un avertissement ;
- il ne doit JAMAIS la ralentir : l'écriture part dans un fil détaché, hors du
  chemin critique de l'utilisateur.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.core.database import get_supabase_client

logger = logging.getLogger(__name__)

TABLE = "copilot_interactions"

# Au-delà, la question est tronquée : un journal n'a pas vocation à stocker un
# copier-coller de plusieurs pages.
MAX_QUESTION_CHARS = 2_000


def enregistrer_tour(
    *,
    company_id: str | None,
    user_id: str | None,
    question: str,
    routage: str,
    outils: list[str],
    latence_ms: int,
    reponse_caracteres: int,
    erreur: str | None = None,
) -> None:
    """Enregistre un tour de conversation. Silencieux en cas d'échec."""
    ligne: dict[str, Any] = {
        "company_id": company_id,
        "user_id": user_id,
        "question": (question or "")[:MAX_QUESTION_CHARS],
        "routage": routage,
        "outils": outils,
        "latence_ms": latence_ms,
        "reponse_caracteres": reponse_caracteres,
        "erreur": erreur,
    }
    threading.Thread(target=_ecrire, args=(ligne,), daemon=True).start()


def _ecrire(ligne: dict[str, Any]) -> None:
    try:
        get_supabase_client().table(TABLE).insert(ligne).execute()
    except Exception as exc:  # noqa: BLE001 - le journal ne bloque jamais
        logger.warning("Journal de l'assistant RH indisponible: %s", exc)

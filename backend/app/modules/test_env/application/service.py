"""
Resynchro de l'environnement de test — logique applicative.

Le backend de test ne détient aucun accès à la base de production : il se
contente de déclencher le workflow GitHub, qui porte seul les identifiants.
C'est ce qui évite de stocker un accès prod dans l'environnement le plus exposé.
"""

from __future__ import annotations

import os
from typing import Optional

import requests

from app.core.logging import get_logger
from app.modules.test_env.domain.exceptions import (
    RefreshDispatchRefused,
    RefreshNotConfigured,
)
from app.modules.test_env.infrastructure.repository import (
    lire_derniere_resynchro as _lire_derniere_resynchro,
)

logger = get_logger("modules.test_env.service")

GITHUB_API = "https://api.github.com"
DISPATCH_EVENT = "refresh-test-env"


def lire_derniere_resynchro() -> Optional[str]:
    """Date de la dernière resynchro réussie, ou None si le journal est vide."""
    return _lire_derniere_resynchro()


def declencher_workflow_resynchro() -> bool:
    """Déclenche le workflow GitHub de resynchro via repository_dispatch."""
    token = os.getenv("GITHUB_DISPATCH_TOKEN", "").strip()
    depot = os.getenv("GITHUB_REPO", "").strip()
    if not token or not depot:
        raise RefreshNotConfigured(
            "Resynchro indisponible : GITHUB_DISPATCH_TOKEN ou GITHUB_REPO "
            "n'est pas configuré sur ce service."
        )

    reponse = requests.post(
        f"{GITHUB_API}/repos/{depot}/dispatches",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"event_type": DISPATCH_EVENT},
        timeout=30,
    )
    if reponse.status_code not in (200, 204):
        logger.error(
            "Déclenchement resynchro refusé : %s %s",
            reponse.status_code,
            reponse.text,
        )
        raise RefreshDispatchRefused(
            "Déclenchement de la resynchro refusé par GitHub."
        )
    return True

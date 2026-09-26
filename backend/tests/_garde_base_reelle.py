"""Garde : les tests d'intégration et e2e ne touchent jamais une vraie base.

Ces tests passent par l'application réelle et par le client Supabase : lancés
avec le `.env` d'un poste, ils écrivent dans la base qu'il désigne. Depuis
septembre 2026, la base de test porte la paie réelle d'un client ; plusieurs
fichiers de `integration/legacy` y ont déjà écrit (deux PDF fictifs dans le
Storage, des crédits de repos recalculés sur le premier salarié venu).

Règle : si l'URL Supabase effective est une vraie base (`*.supabase.co`, hors
l'hôte factice de la CI), la collecte s'arrête avant d'importer le moindre
module de test. Pour lancer ces tests sur une base jetable créée pour ça, poser
explicitement `EYWAI_TESTS_BASE_REELLE=oui`.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

import pytest

HOTE_FACTICE_CI = "ci-fake.supabase.co"
VARIABLE_DEROGATION = "EYWAI_TESTS_BASE_REELLE"


def vise_une_vraie_base(url: str | None) -> bool:
    """Vrai si l'URL désigne un projet Supabase hébergé réel."""
    hote = (urlparse(url or "").hostname or "").lower()
    if not hote or hote == HOTE_FACTICE_CI:
        return False
    return hote.endswith(".supabase.co")


def refuser_une_vraie_base(dossier: str) -> None:
    """À appeler en tête du conftest d'un dossier de tests qui écrit en base."""
    if os.environ.get(VARIABLE_DEROGATION, "").strip().lower() == "oui":
        return
    url = os.environ.get("SUPABASE_URL", "")
    if vise_une_vraie_base(url):
        pytest.exit(
            f"Tests {dossier} refusés : SUPABASE_URL désigne une vraie base "
            f"({urlparse(url).hostname}). Ils y écriraient. Pour une base "
            f"jetable créée pour ça, poser {VARIABLE_DEROGATION}=oui.",
            returncode=2,
        )

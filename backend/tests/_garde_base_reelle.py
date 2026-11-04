"""Garde : les tests d'intégration et e2e ne touchent jamais une vraie base.

Ces tests passent par l'application réelle et par le client Supabase : lancés
avec le `.env` d'un poste, ils écrivent dans la base qu'il désigne. Depuis
septembre 2026, la base de test porte la paie réelle d'un client ; plusieurs
fichiers de `integration/legacy` y ont déjà écrit (deux PDF fictifs dans le
Storage, des crédits de repos recalculés sur le premier salarié venu).

Le 3 novembre 2026, la suite unitaire lancée sur un poste envoyait environ
181 requêtes par passage à la base du `.env` (huit lignes factices écrites dans
`audit_logs`) : un test qui oublie une doublure atteignait la paie réelle.

Règles :
1. `imposer_la_base_factice()`, appelée par `tests/conftest.py` avant tout import
   de l'application, pose les valeurs factices de la CI : le `.env` du poste ne
   peut plus les remplacer (`load_dotenv` ne réécrit jamais une variable posée).
2. Si l'URL Supabase effective est une vraie base (`*.supabase.co`, hors l'hôte
   factice), la collecte s'arrête avant d'importer le moindre module de test.
3. Pour lancer les tests d'intégration ou e2e sur une base jetable créée pour ça,
   poser explicitement `MARTINE_TESTS_BASE_REELLE=oui` (l'ancien nom
   `EYWAI_TESTS_BASE_REELLE` reste lu). Les tests unitaires n'ont pas de dérogation.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

import pytest

HOTE_FACTICE_CI = "ci-fake.supabase.co"
VARIABLE_DEROGATION = "MARTINE_TESTS_BASE_REELLE"
ANCIENNE_VARIABLE_DEROGATION = "EYWAI_TESTS_BASE_REELLE"


# Mêmes valeurs que le job backend de `.github/workflows/ci.yml`.
VALEURS_FACTICES = {
    "SUPABASE_URL": f"https://{HOTE_FACTICE_CI}",
    "SUPABASE_KEY": "ci-fake-anon-key",
    "SUPABASE_SERVICE_KEY": "",
    "SUPABASE_SERVICE_ROLE_KEY": "",
    "OPENROUTER_API_KEY": "sk-or-ci-fake",
    "OPENAI_API_KEY": "",
}


def derogation_posee() -> bool:
    """Vrai si l'on a explicitement demandé une base réelle (jetable)."""
    valeur = os.environ.get(VARIABLE_DEROGATION) or os.environ.get(ANCIENNE_VARIABLE_DEROGATION) or ""
    return valeur.strip().lower() == "oui"


def imposer_la_base_factice() -> None:
    """Pose les valeurs factices avant tout import de l'application, sauf dérogation."""
    if derogation_posee():
        return
    os.environ.update(VALEURS_FACTICES)


def vise_une_vraie_base(url: str | None) -> bool:
    """Vrai si l'URL désigne un projet Supabase hébergé réel."""
    hote = (urlparse(url or "").hostname or "").lower()
    if not hote or hote == HOTE_FACTICE_CI:
        return False
    return hote.endswith(".supabase.co")


def refuser_une_vraie_base(dossier: str, *, derogation_permise: bool = True) -> None:
    """À appeler en tête du conftest d'un dossier de tests qui écrit en base."""
    if derogation_permise and derogation_posee():
        return
    url = os.environ.get("SUPABASE_URL", "")
    if vise_une_vraie_base(url):
        conseil = (
            f"Pour une base jetable créée pour ça, poser {VARIABLE_DEROGATION}=oui."
            if derogation_permise
            else f"Les tests {dossier} n'ont pas de dérogation : les lancer sans {VARIABLE_DEROGATION}."
        )
        pytest.exit(
            f"Tests {dossier} refusés : SUPABASE_URL désigne une vraie base "
            f"({urlparse(url).hostname}). Ils y écriraient. {conseil}",
            returncode=2,
        )

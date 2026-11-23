"""Accès en consultation : un compte qui voit tout ce que son rôle voit, et ne modifie rien.

C'est l'accès d'un contrôleur externe (l'expert-comptable qui vérifie les paies). Son accès
porte le marqueur `user_company_accesses.lecture_seule`. Le refus se fait au seul point
par lequel passent toutes les routes authentifiées, `get_current_user` : une modification
n'a pas à être pensée route par route pour être refusée.

Une lecture passe (GET, HEAD, OPTIONS), sauf les PDF d'identifiants des salariés : leur
lecture peut créer le compte d'un salarié ou remplacer son mot de passe, et le PDF donne un
mot de passe provisoire. Parmi les envois, seuls passent ceux qui ne modifient rien de la
paie : la session (déconnexion, mot de passe), les notifications lues, le choix de la
société, le support, et les lectures envoyées en POST (aperçus d'export, simulations, calcul
des variables à blanc). Les exports qu'elle télécharge ne laissent aucune trace dans
l'historique de la société (`exports.application.commands`) ; les fichiers de virement
bancaire lui sont refusés.

Quelques lectures mettent à jour des données dérivées, comme pour tout autre lecteur : les
empreintes d'un bulletin resté identique, les droits CP d'ancienneté d'un réglage actif, la
période IJSS du mois, la liste d'accueil d'un salarié. Le résultat ne dépend pas de qui
regarde ; aucun montant de paie ne change.

Le chemin testé est celui du routage (`scope["path"]`), pas `request.url.path`, qui couperait
à un « ? » encodé dans le chemin.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

MESSAGE_CONSULTATION = (
    "Accès en consultation : vous pouvez tout voir, mais rien modifier."
)

_METHODES_DE_LECTURE = frozenset({"GET", "HEAD", "OPTIONS"})

# (méthode, chemin) des envois qui ne modifient rien de la paie.
_ENVOIS_PERMIS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (methode, re.compile(motif))
    for methode, motif in (
        ("POST", r"/api/auth/(logout|change-password)"),
        ("POST", r"/api/client-errors"),
        ("PUT", r"/api/notifications/(read-all|[^/]+/read)"),
        ("PATCH", r"/api/users/set-primary-company"),
        ("POST", r"/api/support/tickets"),
        ("POST", r"/api/exports/preview"),
        ("POST", r"/api/exports/generate"),
        ("POST", r"/api/simulation/(arret-maladie|reverse-calculation)"),
        ("POST", r"/api/simulation/[^/]+/compare"),
    )
)

# Lectures refusées : les PDF d'identifiants des salariés.
_LECTURES_REFUSEES: tuple[re.Pattern[str], ...] = (
    re.compile(r"/api/employees/[^/]+/credentials-pdf(/content)?"),
)

# Exports refusés : les fichiers de virement bancaire (IBAN des salariés).
EXPORTS_REFUSES_EN_CONSULTATION = frozenset({"virement_salaires", "virement_acomptes"})

_VRAI = {"1", "true", "yes", "on"}


def permis_en_consultation(
    methode: str, chemin: str, parametres: Mapping[str, str]
) -> bool:
    """Vrai si un compte en consultation peut faire cette requête."""
    methode = methode.upper()
    chemin = chemin.rstrip("/") or "/"
    if methode in _METHODES_DE_LECTURE:
        return not any(motif.fullmatch(chemin) for motif in _LECTURES_REFUSEES)
    if methode == "POST" and chemin == "/api/payroll-variables/generate":
        # Le calcul des variables à blanc (« Simuler le mois ») n'écrit rien.
        return str(parametres.get("dry_run", "")).lower() in _VRAI
    return any(
        methode == m and motif.fullmatch(chemin) for m, motif in _ENVOIS_PERMIS
    )

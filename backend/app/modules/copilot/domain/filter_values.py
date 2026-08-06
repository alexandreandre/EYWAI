"""
Rapprochement des valeurs de filtre proposées par le LLM et des valeurs réelles.

Le modèle écrit « Apprenti », la base contient « Apprentissage » ; il écrit
« maladie », la base contient « arret_maladie » ; il écrit « validé », la base
contient « validated ». Sans rapprochement, une requête bien formée renvoie zéro
ligne et l'assistant répond « aucun apprenti » à une entreprise qui en a deux —
une réponse fausse, plus grave qu'une erreur visible.

Logique purement domaine : aucun accès base, réseau ou LLM.
"""

from __future__ import annotations

import unicodedata

# Énumérations Postgres ``absence_type`` et ``absence_status`` : le LLM ne peut
# pas les deviner, et une valeur hors énumération fait échouer la requête.
ABSENCE_TYPES = (
    "conge_paye",
    "rtt",
    "sans_solde",
    "repos_compensateur",
    "evenement_familial",
    "arret_maladie",
    "arret_at",
    "arret_paternite",
    "arret_maternite",
    "arret_maladie_pro",
)
ABSENCE_STATUTS = ("pending", "validated", "rejected", "cancelled")

# Formulations courantes côté utilisateur -> valeur réelle.
_SYNONYMES: dict[str, str] = {
    "maladie": "arret_maladie",
    "arret": "arret_maladie",
    "accident du travail": "arret_at",
    "at": "arret_at",
    "maladie professionnelle": "arret_maladie_pro",
    "conges": "conge_paye",
    "conges payes": "conge_paye",
    "cp": "conge_paye",
    "maternite": "arret_maternite",
    "paternite": "arret_paternite",
    "mariage": "evenement_familial",
    "deces": "evenement_familial",
    "recuperation": "repos_compensateur",
    "valide": "validated",
    "validee": "validated",
    "accepte": "validated",
    "en attente": "pending",
    "attente": "pending",
    "refuse": "rejected",
    "refusee": "rejected",
    "annule": "cancelled",
}


class ValeurDeFiltreInconnue(ValueError):
    """La valeur proposée ne correspond à aucune valeur acceptée."""


def _replier(valeur: str) -> str:
    """Minuscules, sans accents, séparateurs unifiés."""
    decompose = unicodedata.normalize("NFD", str(valeur).strip().lower())
    sans_accents = "".join(
        c for c in decompose if unicodedata.category(c) != "Mn"
    )
    return sans_accents.replace("_", " ").replace("-", " ").strip()


def rapprocher(valeur: str, valeurs_reelles: tuple[str, ...] | list[str]) -> str | None:
    """Rapproche une valeur d'une liste, sans tenir compte de casse ni d'accents.

    Essaie, dans l'ordre : égalité repliée, synonyme connu, puis préfixe — c'est
    ce dernier qui relie « apprenti » à « Apprentissage ».
    """
    if not valeur:
        return None
    repliee = _replier(valeur)
    if not repliee:
        return None

    par_repli = {_replier(v): v for v in valeurs_reelles}
    if repliee in par_repli:
        return par_repli[repliee]

    synonyme = _SYNONYMES.get(repliee)
    if synonyme and _replier(synonyme) in par_repli:
        return par_repli[_replier(synonyme)]

    prefixes = [
        reelle
        for repli, reelle in par_repli.items()
        if repli.startswith(repliee) or repliee.startswith(repli)
    ]
    if len(prefixes) == 1:
        return prefixes[0]
    return None


def exiger(valeur: str, valeurs_reelles: tuple[str, ...] | list[str], *, champ: str) -> str:
    """Comme ``rapprocher``, mais échoue explicitement plutôt qu'en silence."""
    resolue = rapprocher(valeur, valeurs_reelles)
    if resolue is None:
        acceptees = ", ".join(sorted(valeurs_reelles)) or "aucune"
        raise ValeurDeFiltreInconnue(
            f"Valeur « {valeur} » inconnue pour {champ}. Valeurs possibles : {acceptees}."
        )
    return resolue

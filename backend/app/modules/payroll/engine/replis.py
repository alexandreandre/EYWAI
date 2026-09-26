"""Replis signalés : un calcul qui n'a pas pu se faire doit se voir sur le bulletin.

Quand une lecture échoue pendant la génération (réglages du maintien de
salaire, avances à rembourser, dossier de sortie), le moteur continue et
produit un bulletin plausible. Jusqu'ici, la seule trace était un log, parfois
rien. Chaque repli ajoute désormais une alerte au bulletin, dans la liste
`alertes_baremes` que les RH voient à la génération.

Première étape, volontairement non bloquante : l'alerte se voit, la
génération n'est pas empêchée. Le blocage viendra une fois vérifié qu'aucun de
ces replis ne se produit en temps normal (audit du 25/09/2026, constats B3 à
B6 ; plan, axe 5).

Les calculs qui n'ont pas le contexte de paie sous la main (chargeurs de
règles, lectures de bulletins passés, pied de page) notent leur repli avec
`noter_repli(code)` : le générateur ouvre une collecte pour la durée d'une
génération et reporte ce qui a été noté dans les alertes du bulletin. Hors
génération (écrans, simulations, scripts), `noter_repli` ne fait rien de plus
que le log déjà écrit par l'appelant.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any, Dict, List, Optional

CODE_REPLI_MAINTIEN = "repli_maintien_salaire"
CODE_REPLI_AVANCES = "repli_avances"
CODE_REPLI_SORTIE = "repli_indemnites_sortie"
CODE_REPLI_MUTUELLE = "repli_mutuelle"
CODE_REPLI_CONVENTION = "repli_convention_collective"
CODE_REPLI_EVOLUTION_SALAIRE = "repli_evolution_salaire"
CODE_REPLI_MODULATION = "repli_modulation"
CODE_REPLI_PRIMES_POSTES = "repli_primes_postes"
CODE_REPLI_CONGES_FIN_CONTRAT = "repli_conges_fin_contrat"
CODE_REPLI_PRORATA_ANCIENNETE = "repli_prorata_prime_anciennete"
CODE_REPLI_FORFAIT_ANCIENNETE = "repli_forfait_conges_anciennete"
CODE_REPLI_REFERENCE_CONGES = "repli_reference_conges"
CODE_REPLI_SOLDES_CONGES = "repli_soldes_conges"
CODE_REPLI_VARIABLES_AUTO = "repli_variables_auto"
CODE_REPLI_REGLAGES_CONGES = "repli_reglages_conges"

_MESSAGES: Dict[str, str] = {
    CODE_REPLI_MAINTIEN: (
        "Maintien de salaire non calculé : une erreur a empêché le calcul. "
        "L'arrêt est retiré sans maintien ni indemnités journalières. "
        "À vérifier avant de valider ce bulletin."
    ),
    CODE_REPLI_AVANCES: (
        "Remboursements d'avances non calculés : une erreur a empêché le calcul. "
        "Aucune avance n'est retenue sur ce bulletin. "
        "À vérifier avant de le valider."
    ),
    CODE_REPLI_SORTIE: (
        "Dossier de sortie non lu : une erreur a empêché sa lecture. "
        "Le bulletin est calculé comme un mois ordinaire, sans indemnités de sortie. "
        "À vérifier avant de le valider."
    ),
    CODE_REPLI_MUTUELLE: (
        "Mutuelle non lue : une erreur a empêché de lire les garanties du salarié. "
        "Les parts de mutuelle, et leur effet sur la CSG et le net imposable, "
        "peuvent manquer. À vérifier avant de valider ce bulletin."
    ),
    CODE_REPLI_CONVENTION: (
        "Règles de la convention collective lues en partie seulement : prime "
        "d'ancienneté, minima ou heures supplémentaires conventionnelles peuvent "
        "manquer. À vérifier avant de valider ce bulletin."
    ),
    CODE_REPLI_EVOLUTION_SALAIRE: (
        "Évolution de salaire non lue : le salaire de base de la fiche est utilisé, "
        "sans prorata de changement de salaire ni rappel. "
        "À vérifier avant de valider ce bulletin."
    ),
    CODE_REPLI_MODULATION: (
        "Durées hebdomadaires de modulation non lues : les heures supplémentaires "
        "sont calculées sur la durée du contrat. "
        "À vérifier avant de valider ce bulletin."
    ),
    CODE_REPLI_PRIMES_POSTES: (
        "Primes de poste non recalculées sur la fenêtre des variables : le résumé "
        "enregistré avec le planning est repris, ou rien s'il manque. "
        "À vérifier avant de valider ce bulletin."
    ),
    CODE_REPLI_CONGES_FIN_CONTRAT: (
        "Indemnité de congés de fin de contrat calculée sans toutes ses données : "
        "compteurs de congés ou rémunération de la période précédente illisibles. "
        "À vérifier avant de valider ce bulletin."
    ),
    CODE_REPLI_PRORATA_ANCIENNETE: (
        "Jours de maintien non calculés : la prime d'ancienneté n'est pas "
        "proratisée sur l'arrêt. À vérifier avant de valider ce bulletin."
    ),
    CODE_REPLI_FORFAIT_ANCIENNETE: (
        "Congés d'ancienneté non lus : le forfait annuel en jours n'en est pas "
        "réduit. À vérifier avant de valider ce bulletin."
    ),
    CODE_REPLI_REFERENCE_CONGES: (
        "Bulletins de la période de référence des congés lus en partie seulement : "
        "l'indemnité de congés au dixième peut être sous-évaluée. "
        "À vérifier avant de valider ce bulletin."
    ),
    CODE_REPLI_SOLDES_CONGES: (
        "Soldes de congés non calculés : le pied du bulletin ne les affiche pas. "
        "À vérifier avant de valider ce bulletin."
    ),
    CODE_REPLI_VARIABLES_AUTO: (
        "Variables de paie automatiques non générées : primes et astreintes issues "
        "du planning peuvent manquer. À vérifier avant de valider ce bulletin."
    ),
    CODE_REPLI_REGLAGES_CONGES: (
        "Réglages de congés de la société non lus : la période de référence est "
        "supposée commencer en juin. À vérifier avant de valider ce bulletin."
    ),
}

# Alertes de repli de la génération en cours (voir `ouvrir_collecte`).
_COLLECTE: ContextVar[Optional[List[Dict[str, Any]]]] = ContextVar(
    "replis_de_la_generation", default=None
)


def alerte_de_repli(code: str) -> Dict[str, Any]:
    """L'alerte d'un repli, au format des autres alertes du bulletin."""
    return {"code": code, "message": _MESSAGES[code], "repli": True}


def _ajouter(alertes: List[Dict[str, Any]], code: str) -> None:
    if any(isinstance(a, dict) and a.get("code") == code for a in alertes):
        return
    alertes.append(alerte_de_repli(code))


def signaler_repli(contexte: Any, code: str) -> None:
    """Ajoute l'alerte au contexte de paie (reprise dans le bulletin final)."""
    alertes = getattr(contexte, "alertes_baremes", None)
    if not isinstance(alertes, list):
        alertes = []
        contexte.alertes_baremes = alertes
    _ajouter(alertes, code)


def ajouter_repli(alertes: List[Dict[str, Any]], code: str) -> None:
    """Ajoute l'alerte à une liste d'alertes déjà constituée."""
    _ajouter(alertes, code)


def ouvrir_collecte(alertes: List[Dict[str, Any]]) -> Token:
    """Pour la durée d'une génération : les replis notés vont dans `alertes`.

    Rendre le jeton à `fermer_collecte`, dans un `finally`.
    """
    return _COLLECTE.set(alertes)


def fermer_collecte(jeton: Token) -> None:
    _COLLECTE.reset(jeton)


def noter_repli(code: str) -> None:
    """Note un repli pour la génération en cours ; sans génération, ne fait rien."""
    alertes = _COLLECTE.get()
    if alertes is not None:
        _ajouter(alertes, code)


def fusionner_replis(
    alertes_du_bulletin: List[Any] | None, replis: List[Dict[str, Any]]
) -> List[Any]:
    """Les alertes du bulletin, plus les replis qui n'y sont pas déjà."""
    fusion = list(alertes_du_bulletin or [])
    for repli in replis:
        _ajouter(fusion, repli["code"])
    return fusion

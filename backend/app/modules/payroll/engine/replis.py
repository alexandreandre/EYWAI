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
"""

from __future__ import annotations

from typing import Any, Dict, List

CODE_REPLI_MAINTIEN = "repli_maintien_salaire"
CODE_REPLI_AVANCES = "repli_avances"
CODE_REPLI_SORTIE = "repli_indemnites_sortie"

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
}


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

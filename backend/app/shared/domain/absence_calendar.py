"""Vocabulaire partagé des jours de planning issus d'une absence validée.

Un jour de `planned_calendar` peut porter des métadonnées d'absence : nature de
l'arrêt, subrogation, historique des arrêts de l'année, vrai début d'un arrêt
multi-mois… Ces clés sont écrites par la validation d'absence et lues par le
moteur de paie (maintien de salaire, IJSS). Elles sont donc **propriété du
serveur** : une écriture de planning les reprend depuis l'entrée stockée et ne
les lit jamais du payload entrant, sans quoi n'importe quel porteur de
`schedules.update` pourrait fabriquer un arrêt de travail — ou « copier le mois
précédent » rejouer un arrêt sur un mois qui n'en a pas.

Ce module est pur (aucune I/O) et volontairement neutre : il est partagé par
schedules (fusion, régénération, import de pointages), absences (pose du
marqueur) et les scripts de reprise, qui en dupliquaient jusqu'ici des variantes
divergentes.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

# Valeur du marqueur de provenance posé sur un jour issu d'une absence validée.
ORIGINE_ABSENCE = "absence"

# Types de calendrier qu'une validation d'absence peut produire.
# Source : absences.infrastructure.providers.CalendarUpdateProvider
# (`type_mapping` + le cas arrêt de travail).
ABSENCE_CALENDAR_TYPES: frozenset[str] = frozenset(
    {"arret_maladie", "conge", "conges_payes", "rtt"}
)

# Clés d'un jour de planning que seul le serveur écrit.
SERVER_OWNED_ABSENCE_KEYS: frozenset[str] = frozenset(
    {
        "origine",
        "arret_type",
        "subrogation_active",
        "nombre_enfants",
        "historique_arrets_annee",
        "date_debut_arret_reel",
        "salaire_periode_reelle",
    }
)


def is_absence_day(entry: Optional[Mapping[str, Any]]) -> bool:
    """Vrai si le jour est réellement issu d'une absence validée.

    Les deux conditions comptent : un marqueur `origine` posé par erreur sur un
    jour travaillé ne doit pas suffire à le geler contre les régénérations.
    """
    if not entry:
        return False
    return (
        entry.get("origine") == ORIGINE_ABSENCE
        and entry.get("type") in ABSENCE_CALENDAR_TYPES
    )


def strip_server_owned_keys(entry: dict[str, Any]) -> dict[str, Any]:
    """Retire les clés serveur d'un jour (mutation en place, entrée renvoyée)."""
    for cle in SERVER_OWNED_ABSENCE_KEYS:
        entry.pop(cle, None)
    return entry


__all__ = [
    "ABSENCE_CALENDAR_TYPES",
    "ORIGINE_ABSENCE",
    "SERVER_OWNED_ABSENCE_KEYS",
    "is_absence_day",
    "strip_server_owned_keys",
]

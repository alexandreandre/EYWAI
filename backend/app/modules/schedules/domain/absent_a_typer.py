"""Jour « absent, type à donner » (case « absent » de l'import de pointages).

Retour d'Elsa du 28/10/2026 : en dépliant une ligne de l'import, un jour vide
peut être coché « absent » ; il passe en rouge au calendrier et bloque la paie.
La marque vit dans le TYPE du jour prévu : elle ne retire rien du salaire par
elle-même (aucune branche du moteur ne la lit), et la génération la refuse
sans forçage possible tant que la RH ne lui a pas donné son vrai type
(congé, RTT, arrêt ou absence non payée), qui la remplace.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

from app.modules.schedules.domain.conflits_arret import libelle_des_dates

TYPE_ABSENT_A_TYPER = "absent_a_typer"


def est_absent_a_typer(entree: object) -> bool:
    return isinstance(entree, dict) and entree.get("type") == TYPE_ABSENT_A_TYPER


def message_absents_a_typer(prenom: str, jours: Iterable[date]) -> str:
    """La phrase du refus : qui, quels jours, quoi faire."""
    dates = sorted(set(jours))
    debut = (
        f"{prenom} a un jour marqué « absent » sans type"
        if len(dates) == 1
        else f"{prenom} a des jours marqués « absent » sans type"
    )
    quand = libelle_des_dates((d.year, d.month, d.day) for d in dates)
    return (
        f"{debut} : {quand}. Donnez le type de chaque jour dans le calendrier "
        "(congé, RTT, arrêt ou absence non payée) : la paie reste bloquée jusque-là."
    )


__all__ = ["TYPE_ABSENT_A_TYPER", "est_absent_a_typer", "message_absents_a_typer"]

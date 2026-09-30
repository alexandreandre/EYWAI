"""Filet du moteur : les heures saisies un jour d'arrêt sont écartées du calcul.

Le 30/09/2026, une salariée en arrêt tout septembre a reçu 70,75 h sup à 50 % :
des heures pointées restaient sur ses jours d'arrêt. Deux chemins en faisaient
des heures sup — l'analyse des horaires (`analyzer.analyser_horaires_du_mois`)
et l'option société `compensation_semaines` — et l'arrêt n'était plus retenu
les jours pointés.

La garde de génération refuse ce cas (`payslips.application.commands`), mais le
bac à sable, le suivi IJSS et les jours hors de la période à saisir ne passent
pas par elle. Le générateur écarte donc ces heures **une fois**, à la source
commune des deux chemins (le réel des trois mois lus, avant le repli planning),
avec la même règle que la garde (`schedules.domain.conflits_arret`). Le bulletin
le dit.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.core.logging import get_logger
from app.modules.payroll.engine.replis import CODE_REPLI_ARRETS_ILLISIBLES, noter_repli
from app.modules.schedules.domain.conflits_arret import (
    JourEnConflit,
    arrets_necessaires,
    ecarter_heures_en_conflit,
    message_heures_ecartees,
)
from app.modules.schedules.infrastructure.arrets_valides import arrets_valides_reader

logger = get_logger("modules.payroll.application.heures_sur_arret")

#: Code de l'alerte posée sur le bulletin (`payslip_data.alertes_baremes`).
CODE_ALERTE_HEURES_ECARTEES = "heures_sur_arret_ecartees"


@dataclass(frozen=True)
class HeuresEcartees:
    #: Le réel à calculer : les heures des jours en conflit remises à 0.
    reel: list[dict]
    #: Les jours écartés, triés par date.
    jours: tuple[JourEnConflit, ...] = ()


def ecarter_heures_sur_arret(
    employee_id: str,
    calendrier_prevu: list[dict],
    calendrier_reel: list[dict],
    debut: date,
    fin: date,
) -> HeuresEcartees:
    """Le réel sans les heures des jours d'arrêt ou d'absence non travaillée.

    Les arrêts validés (`[debut, fin]`) ne sont lus que si un week-end, un repos
    ou un férié porte des heures : ce sont les seuls jours qu'ils rattachent à un
    arrêt. S'ils ne peuvent pas être lus, le moteur n'invente rien : la règle du
    type prévu s'applique seule, et le bulletin porte un repli.
    """
    arrets = None
    if arrets_necessaires(calendrier_prevu, calendrier_reel):
        try:
            arrets = arrets_valides_reader.par_salarie([employee_id], debut, fin).get(
                str(employee_id), []
            )
        except Exception:
            logger.warning(
                "Arrêts validés illisibles (salarié %s) : seules les heures des jours "
                "d'arrêt du planning sont écartées",
                employee_id,
                exc_info=True,
            )
            noter_repli(CODE_REPLI_ARRETS_ILLISIBLES)
    reel, jours = ecarter_heures_en_conflit(calendrier_prevu, calendrier_reel, arrets)
    if jours:
        logger.info(
            "Heures saisies un jour d'arrêt écartées du calcul (salarié %s) : %s",
            employee_id,
            [j.en_detail() for j in jours],
        )
    return HeuresEcartees(reel, tuple(jours))


def _date(jour: JourEnConflit) -> date | None:
    try:
        return date(int(jour.annee), int(jour.mois), int(jour.jour))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def alerte_heures_ecartees(
    jours: Sequence[JourEnConflit],
    debut_periode: date,
    fin_periode: date,
) -> dict[str, Any] | None:
    """L'alerte du bulletin, ou None.

    Elle nomme les jours écartés des semaines de la période (mois civil ∪ fenêtre
    des variables), du lundi de son premier jour au dimanche de son dernier : les
    heures sup se comptent par semaine, ce sont les seuls jours qui peuvent
    changer ce bulletin.
    """
    lundi = debut_periode - timedelta(days=debut_periode.weekday())
    dimanche = fin_periode + timedelta(days=6 - fin_periode.weekday())
    retenus = [j for j in jours if (d := _date(j)) is not None and lundi <= d <= dimanche]
    if not retenus:
        return None
    return {
        "code": CODE_ALERTE_HEURES_ECARTEES,
        "critique": False,
        "severity": "warning",
        "message": message_heures_ecartees(retenus),
        "jours": [j.en_detail() for j in retenus],
    }


__all__ = [
    "CODE_ALERTE_HEURES_ECARTEES",
    "HeuresEcartees",
    "alerte_heures_ecartees",
    "ecarter_heures_sur_arret",
]

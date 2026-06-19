"""Arbitrage indemnité congés payés : maintien de salaire vs règle du 1/10e."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.core.logging import get_logger, log_payroll_debug

logger = get_logger("modules.payroll.engine.iccp_arbitrage")

MethodeRetenue = Literal["maintien", "dixieme"]


@dataclass
class MaintienHoraireDetail:
    heures_normales: float = 0.0
    heures_hs: float = 0.0
    part_normale: float = 0.0
    part_hs: float = 0.0
    total: float = 0.0


@dataclass
class IccpArbitrageResult:
    montant_final: float
    methode_retenue: MethodeRetenue
    indemnite_maintien: float
    indemnite_dixieme: float
    taux_journalier: float | None = None
    valeur_jour_dixieme: float = 0.0
    base_reference_dixieme: float = 0.0
    jours_restants: float = 0.0
    maintien_horaire: MaintienHoraireDetail | None = None
    alertes: list[str] = field(default_factory=list)


def lire_parametres_conges(baremes: dict | None) -> dict[str, float]:
    cfg = (baremes or {}).get("conges", {}) or {}
    return {
        "taux_dixieme": float(cfg.get("taux_dixieme", 0.10)),
        "jours_reference_dixieme": float(cfg.get("jours_reference_dixieme", 30.0)),
        "taux_journalier_diviseur": float(cfg.get("taux_journalier_diviseur", 21.67)),
    }


def calculer_maintien_journalier(jours: float, taux_journalier: float) -> float:
    if jours <= 0 or taux_journalier <= 0:
        return 0.0
    return round(jours * taux_journalier, 2)


def calculer_maintien_horaire(
    nombre_jours: float,
    salaire_horaire_base: float,
    *,
    heures_normales_par_jour: float,
    heures_supp_par_jour: float = 0.0,
    majoration_hs: float = 0.0,
) -> MaintienHoraireDetail:
    if nombre_jours <= 0:
        return MaintienHoraireDetail()

    total_heures_normales = nombre_jours * heures_normales_par_jour
    total_heures_hs = nombre_jours * heures_supp_par_jour
    salaire_horaire_majore = salaire_horaire_base * (1 + majoration_hs)

    part_normale_raw = total_heures_normales * salaire_horaire_base
    part_hs_raw = total_heures_hs * salaire_horaire_majore
    total_raw = part_normale_raw + part_hs_raw

    total = round(total_raw, 2)
    part_hs = round(part_hs_raw, 2)
    part_normale = total - part_hs

    return MaintienHoraireDetail(
        heures_normales=total_heures_normales,
        heures_hs=total_heures_hs,
        part_normale=part_normale,
        part_hs=part_hs,
        total=total,
    )


def calculer_dixieme(
    jours: float,
    base_reference: float,
    *,
    taux: float = 0.10,
    jours_reference: float = 30.0,
) -> tuple[float, float]:
    if jours <= 0 or base_reference <= 0 or jours_reference <= 0:
        return 0.0, 0.0
    valeur_jour = (base_reference * taux) / jours_reference
    return round(jours * valeur_jour, 2), round(valeur_jour, 4)


def arbitrer_iccp(
    jours_restants: float,
    indemnite_maintien: float,
    indemnite_dixieme: float,
    *,
    taux_journalier: float | None = None,
    valeur_jour_dixieme: float = 0.0,
    base_reference_dixieme: float = 0.0,
    maintien_horaire: MaintienHoraireDetail | None = None,
    alertes: list[str] | None = None,
) -> IccpArbitrageResult:
    montant_final = max(indemnite_maintien, indemnite_dixieme)
    if indemnite_dixieme > indemnite_maintien:
        methode: MethodeRetenue = "dixieme"
    else:
        methode = "maintien"

    log_payroll_debug(logger, "\n--- Arbitrage ICCP ---")
    log_payroll_debug(logger, f"\tMaintien : {indemnite_maintien:10.2f} €")
    log_payroll_debug(logger, f"\t1/10e    : {indemnite_dixieme:10.2f} €")
    log_payroll_debug(logger, f"\tRetenu   : {montant_final:10.2f} € ({methode})")

    return IccpArbitrageResult(
        montant_final=round(montant_final, 2),
        methode_retenue=methode,
        indemnite_maintien=round(indemnite_maintien, 2),
        indemnite_dixieme=round(indemnite_dixieme, 2),
        taux_journalier=taux_journalier,
        valeur_jour_dixieme=valeur_jour_dixieme,
        base_reference_dixieme=base_reference_dixieme,
        jours_restants=jours_restants,
        maintien_horaire=maintien_horaire,
        alertes=list(alertes or []),
    )


def arbitrer_iccp_complet(
    jours_restants: float,
    *,
    taux_journalier: float | None = None,
    maintien_horaire: MaintienHoraireDetail | None = None,
    base_reference_dixieme: float = 0.0,
    taux_dixieme: float = 0.10,
    jours_reference_dixieme: float = 30.0,
    alertes: list[str] | None = None,
) -> IccpArbitrageResult:
    if maintien_horaire is not None:
        indemnite_maintien = maintien_horaire.total
    elif taux_journalier is not None:
        indemnite_maintien = calculer_maintien_journalier(jours_restants, taux_journalier)
    else:
        indemnite_maintien = 0.0

    indemnite_dixieme, valeur_jour = calculer_dixieme(
        jours_restants,
        base_reference_dixieme,
        taux=taux_dixieme,
        jours_reference=jours_reference_dixieme,
    )

    return arbitrer_iccp(
        jours_restants,
        indemnite_maintien,
        indemnite_dixieme,
        taux_journalier=taux_journalier,
        valeur_jour_dixieme=valeur_jour,
        base_reference_dixieme=base_reference_dixieme,
        maintien_horaire=maintien_horaire,
        alertes=alertes,
    )

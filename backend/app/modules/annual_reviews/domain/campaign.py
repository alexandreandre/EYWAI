"""
Règles pures : politique de campagne d'entretien annuel, par société.

Chaque société arrête ses entretiens à sa façon — un mois de campagne commun pour la
plupart, la date d'ancienneté pour une autre, un cycle de deux ans pour une troisième.
Ces règles viennent du réglage société (`company_interview_settings`) et non du code :
la RH change son mois de campagne sans passer par nous.

Aucune date n'est déduite tant que la société n'a pas été réglée : `enabled` faux
renvoie systématiquement None, de sorte qu'activer la fonctionnalité ne change rien
pour les sociétés qu'on n'a pas paramétrées.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Literal, Optional

from app.shared.domain.employment_rules import is_forfait_jour

CampaignMode = Literal["mois_fixe", "anniversaire_embauche"]
CampaignUrgency = Literal["due", "overdue"]

MODE_MOIS_FIXE: CampaignMode = "mois_fixe"
MODE_ANNIVERSAIRE: CampaignMode = "anniversaire_embauche"

CADRE_STATUTS = frozenset({"cadre", "cadre au forfait jour"})


@dataclass(frozen=True)
class InterviewCampaignSettings:
    """Politique d'entretien d'une société. Miroir de company_interview_settings."""

    enabled: bool = False
    campaign_mode: str = MODE_MOIS_FIXE
    campaign_month: Optional[int] = None
    periodicity_years: int = 1

    @classmethod
    def from_row(cls, row: Optional[Dict[str, Any]]) -> "InterviewCampaignSettings":
        """Une société sans ligne de réglage retombe sur le défaut inerte."""
        if not row:
            return DEFAULT_CAMPAIGN_SETTINGS
        mois = row.get("campaign_month")
        return cls(
            enabled=bool(row.get("enabled", False)),
            campaign_mode=str(row.get("campaign_mode") or MODE_MOIS_FIXE),
            campaign_month=int(mois) if mois is not None else None,
            periodicity_years=int(row.get("periodicity_years") or 1),
        )


DEFAULT_CAMPAIGN_SETTINGS = InterviewCampaignSettings()


def deduce_interview_type(
    statut: Optional[str], forfait_jour: Optional[bool] = None
) -> str:
    """Type d'entretien attendu pour un salarié, déduit de son statut.

    Même règle que `compute_planning_suggestions`, pour que la reprise de données et
    les suggestions ne se contredisent jamais. Le forfait jour prime sur le statut
    cadre : c'est l'entretien de suivi de charge qui est obligatoire, pas l'annuel.
    """
    if is_forfait_jour(statut, forfait_jour):
        return "annual_forfait_jour"
    if statut and statut.strip().lower() in CADRE_STATUTS:
        return "annual_cadres"
    return "annual_performance"


def _anniversaire(reference: date, annee: int) -> date:
    """Même jour et mois qu'à l'embauche. Un 29 février retombe sur le 28."""
    try:
        return date(annee, reference.month, reference.day)
    except ValueError:
        return date(annee, reference.month, 28)


def next_campaign_date(
    settings: InterviewCampaignSettings,
    hire_date: Optional[date],
    last_review_year: Optional[int],
    today: date,
) -> Optional[date]:
    """Date du prochain entretien à planifier, ou None si rien n'est déductible.

    Une échéance déjà dépassée est renvoyée telle quelle, dans le passé : la repousser
    à l'occurrence suivante masquerait précisément le retard qu'il faut voir.
    """
    if not settings.enabled:
        return None

    periodicite = max(1, settings.periodicity_years)

    if settings.campaign_mode == MODE_MOIS_FIXE:
        mois = settings.campaign_month
        if mois is None or not 1 <= mois <= 12:
            return None
        if last_review_year is not None:
            return date(last_review_year + periodicite, mois, 1)
        annee = today.year if mois >= today.month else today.year + 1
        return date(annee, mois, 1)

    if settings.campaign_mode == MODE_ANNIVERSAIRE:
        if hire_date is None:
            return None
        if last_review_year is not None:
            return _anniversaire(hire_date, last_review_year + periodicite)
        annee = max(today.year, hire_date.year + periodicite)
        echeance = _anniversaire(hire_date, annee)
        if echeance < today:
            echeance = _anniversaire(hire_date, annee + periodicite)
        return echeance

    return None


def campaign_urgency(echeance: date, today: date) -> CampaignUrgency:
    """Une échéance passée est en retard ; le jour même compte encore comme à venir."""
    return "overdue" if echeance < today else "due"

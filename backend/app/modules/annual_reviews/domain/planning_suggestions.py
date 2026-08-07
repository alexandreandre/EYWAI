"""
Règles pures : entretiens annuels cadres / forfait jour à planifier.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, TypedDict

from app.modules.annual_reviews.domain.campaign import (
    DEFAULT_CAMPAIGN_SETTINGS,
    InterviewCampaignSettings,
    campaign_urgency,
    deduce_interview_type,
    next_campaign_date,
)
from app.modules.annual_reviews.domain.interview_types import (
    ACTIVE_OR_COMPLETED_REVIEW_STATUSES,
    COMPLETED_REVIEW_STATUSES,
    INTERVIEW_TYPE_LABELS,
)
from app.shared.domain.employment_rules import is_forfait_jour

PlanningUrgency = Literal["due", "overdue"]

CADRE_STATUTS = frozenset({"cadre", "cadre au forfait jour"})


class PlanningSuggestion(TypedDict):
    employee_id: str
    employee_name: str
    interview_type: str
    interview_type_label: str
    reason: str
    urgency: PlanningUrgency
    year: int
    # Date proposée par la campagne de la société, ISO. None hors campagne réglée :
    # la RH choisit alors elle-même le jour.
    planned_date: str | None


def _employee_display_name(row: Dict[str, Any]) -> str:
    fn = str(row.get("first_name") or "").strip()
    ln = str(row.get("last_name") or "").strip()
    return f"{fn} {ln}".strip() or "Collaborateur"


def is_cadre(statut: str | None) -> bool:
    """True si le statut indique un cadre (y compris cadre au forfait jour)."""
    if not statut:
        return False
    return statut.strip().lower() in CADRE_STATUTS


def _is_active_employee(row: Dict[str, Any]) -> bool:
    st = row.get("employment_status")
    if st is None:
        return True
    if st in ("parti", "en_sortie"):
        return False
    return st == "actif"


def _has_covered_review(
    reviews: List[Dict[str, Any]],
    employee_id: str,
    interview_type: str,
    year: int,
) -> bool:
    for row in reviews:
        if str(row.get("employee_id")) != employee_id:
            continue
        if str(row.get("interview_type") or "") != interview_type:
            continue
        if int(row.get("year") or 0) != year:
            continue
        if str(row.get("status") or "") in ACTIVE_OR_COMPLETED_REVIEW_STATUSES:
            return True
    return False


def _urgency_for_year(year: int, today: date) -> PlanningUrgency:
    """Après le 30 juin, une absence de planification devient « overdue »."""
    if today.year > year:
        return "overdue"
    if today.year < year:
        return "due"
    if today.month > 6 or (today.month == 6 and today.day > 30):
        return "overdue"
    return "due"


def _trier(suggestions: List[PlanningSuggestion]) -> List[PlanningSuggestion]:
    """Les retards d'abord, puis par ordre alphabétique."""
    order = {"overdue": 0, "due": 1}
    suggestions.sort(
        key=lambda s: (order.get(s["urgency"], 9), s["employee_name"].lower())
    )
    return suggestions


def _last_completed_year(
    reviews: List[Dict[str, Any]], employee_id: str, interview_type: str
) -> int | None:
    """Année du dernier entretien réellement tenu, du même type. None si aucun."""
    annees = [
        int(row.get("year") or 0)
        for row in reviews
        if str(row.get("employee_id")) == employee_id
        and str(row.get("interview_type") or "") == interview_type
        and str(row.get("status") or "") in COMPLETED_REVIEW_STATUSES
    ]
    annees = [a for a in annees if a]
    return max(annees) if annees else None


def _parse_hire_date(valeur: Any) -> date | None:
    if isinstance(valeur, date):
        return valeur
    if not valeur:
        return None
    try:
        return date.fromisoformat(str(valeur)[:10])
    except ValueError:
        return None


def _campaign_suggestions(
    employees: List[Dict[str, Any]],
    reviews: List[Dict[str, Any]],
    year: int,
    ref: date,
    settings: InterviewCampaignSettings,
) -> List[PlanningSuggestion]:
    """Campagne réglée par la société : un entretien attendu par salarié actif.

    Le type est déduit du statut, donc un cadre au forfait jour n'est proposé qu'une
    fois — contrairement au comportement historique qui l'inscrivait aux deux.
    """
    suggestions: List[PlanningSuggestion] = []

    for emp in employees:
        if not _is_active_employee(emp):
            continue
        eid = str(emp["id"])
        interview_type = deduce_interview_type(
            emp.get("statut"), emp.get("is_forfait_jour")
        )
        echeance = next_campaign_date(
            settings,
            hire_date=_parse_hire_date(emp.get("hire_date")),
            last_review_year=_last_completed_year(reviews, eid, interview_type),
            today=ref,
        )
        if echeance is None or echeance.year > year:
            continue
        if _has_covered_review(reviews, eid, interview_type, echeance.year):
            continue
        suggestions.append(
            {
                "employee_id": eid,
                "employee_name": _employee_display_name(emp),
                "interview_type": interview_type,
                "interview_type_label": INTERVIEW_TYPE_LABELS[interview_type],
                "reason": (
                    f"Campagne d'entretien de la société : échéance au "
                    f"{echeance.strftime('%d/%m/%Y')}."
                ),
                "urgency": campaign_urgency(echeance, ref),
                "year": echeance.year,
                "planned_date": echeance.isoformat(),
            }
        )
    return suggestions


def compute_planning_suggestions(
    employees: List[Dict[str, Any]],
    reviews: List[Dict[str, Any]],
    year: int,
    today: date | None = None,
    settings: InterviewCampaignSettings | None = None,
) -> List[PlanningSuggestion]:
    """
    Retourne les salariés actifs sans entretien annuel planifié ou réalisé.

    Sans réglage de campagne — le cas de toutes les sociétés tant qu'on ne les a pas
    paramétrées — seuls les cadres et les forfaits jour sont proposés, comme avant.
    Réglage posé, la campagne de la société couvre l'ensemble de son effectif.
    """
    ref = today or date.today()
    reglage = settings or DEFAULT_CAMPAIGN_SETTINGS
    if reglage.enabled:
        return _trier(_campaign_suggestions(employees, reviews, year, ref, reglage))

    suggestions: List[PlanningSuggestion] = []

    for emp in employees:
        if not _is_active_employee(emp):
            continue
        eid = str(emp["id"])
        statut = emp.get("statut")
        name = _employee_display_name(emp)
        urgency = _urgency_for_year(year, ref)

        if is_forfait_jour(statut) and not _has_covered_review(
            reviews, eid, "annual_forfait_jour", year
        ):
            suggestions.append(
                {
                    "employee_id": eid,
                    "employee_name": name,
                    "interview_type": "annual_forfait_jour",
                    "interview_type_label": INTERVIEW_TYPE_LABELS[
                        "annual_forfait_jour"
                    ],
                    "reason": "Entretien annuel de suivi forfait jour non planifié pour cette année.",
                    "urgency": urgency,
                    "year": year,
                    "planned_date": None,
                }
            )

        if is_cadre(statut) and not _has_covered_review(
            reviews, eid, "annual_cadres", year
        ):
            suggestions.append(
                {
                    "employee_id": eid,
                    "employee_name": name,
                    "interview_type": "annual_cadres",
                    "interview_type_label": INTERVIEW_TYPE_LABELS["annual_cadres"],
                    "reason": "Entretien annuel des cadres non planifié pour cette année.",
                    "urgency": urgency,
                    "year": year,
                    "planned_date": None,
                }
            )

    return _trier(suggestions)

"""
Calcul du délai de préavis pour les sorties de salariés.

Priorité : règles conventionnelles extraites (si présentes) → minima légaux (R1234-2 / R1234-3).
Logique pure : aucune I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Literal, Optional

from dateutil.relativedelta import relativedelta

NoticeSource = Literal["legal", "convention", "none", "not_applicable"]
EmployeeCategory = Literal["cadre", "non_cadre"]

MONTH_CALENDAR_DAYS = 30


@dataclass(frozen=True)
class NoticePeriodResult:
    days: int
    source: NoticeSource
    label: str
    detail: str
    warnings: tuple[str, ...] = ()
    collective_agreement_name: Optional[str] = None
    collective_agreement_idcc: Optional[str] = None
    seniority_months: Optional[int] = None
    employee_category: Optional[EmployeeCategory] = None
    applicable: bool = True


def _normalize_idcc(idcc: Any) -> Optional[str]:
    if idcc is None:
        return None
    raw = str(idcc).strip()
    return raw or None


def resolve_employee_category(statut: Any) -> tuple[EmployeeCategory, bool]:
    """
    Déduit cadre / non-cadre depuis le champ statut employé.
    Retourne (catégorie, statut_explicite).
    """
    low = str(statut or "").strip().lower()
    compact = low.replace(" ", "").replace("-", "")
    if not compact:
        return "non_cadre", False
    if "noncadre" in compact:
        return "non_cadre", True
    if "cadre" in compact:
        return "cadre", True
    if "maitrise" in compact or "maîtrise" in low:
        return "non_cadre", True
    if "employe" in compact or "employé" in low or "ouvrier" in compact:
        return "non_cadre", True
    return "non_cadre", False


def compute_seniority_months(hire_date: date, reference_date: date) -> int:
    if reference_date < hire_date:
        return 0
    delta = relativedelta(reference_date, hire_date)
    return max(0, delta.years * 12 + delta.months)


def _months_to_days(months: int) -> int:
    return max(0, months) * MONTH_CALENDAR_DAYS


def _legal_notice_days(
    exit_type: str,
    *,
    category: EmployeeCategory,
    seniority_months: int,
    is_gross_misconduct: bool,
) -> NoticePeriodResult:
    if is_gross_misconduct:
        return NoticePeriodResult(
            days=0,
            source="not_applicable",
            label="Aucun préavis",
            detail="Faute grave ou lourde : pas de préavis ni d'indemnité compensatrice.",
            applicable=False,
        )

    if exit_type in ("rupture_conventionnelle", "depart_retraite"):
        return NoticePeriodResult(
            days=0,
            source="not_applicable",
            label="Préavis non applicable",
            detail=(
                "La rupture conventionnelle et le départ à la retraite ne prévoient pas "
                "de préavis standard — la date de fin est fixée d'un commun accord."
            ),
            applicable=False,
        )

    if exit_type == "fin_periode_essai":
        return NoticePeriodResult(
            days=0,
            source="not_applicable",
            label="Préavis non applicable",
            detail=(
                "En fin de période d'essai, ce sont les délais de prévenance contractuels "
                "ou légaux spécifiques qui s'appliquent (souvent plus courts qu'un préavis classique)."
            ),
            applicable=False,
            warnings=(
                "Vérifiez la durée de prévenance prévue au contrat ou dans la convention collective.",
            ),
        )

    if exit_type not in ("demission", "licenciement"):
        return NoticePeriodResult(
            days=0,
            source="none",
            label="Préavis non déterminé",
            detail="Type de départ non pris en charge pour le calcul automatique du préavis.",
            applicable=False,
        )

    if seniority_months < 6:
        return NoticePeriodResult(
            days=0,
            source="legal",
            label="Aucun préavis légal minimum",
            detail=(
                "Ancienneté inférieure à 6 mois : le Code du travail ne fixe pas de délai "
                "de préavis minimum (sauf dispositions conventionnelles ou contractuelles)."
            ),
            seniority_months=seniority_months,
            employee_category=category,
            warnings=(
                "Une convention collective ou une clause contractuelle peut toutefois prévoir un préavis.",
            ),
        )

    if category == "cadre":
        if seniority_months < 24:
            days = _months_to_days(2)
            detail = (
                "Cadre, ancienneté de 6 mois à moins de 2 ans : préavis légal de 2 mois "
                f"({days} jours calendaires)."
            )
        else:
            days = _months_to_days(3)
            detail = (
                "Cadre, ancienneté d'au moins 2 ans : préavis légal de 3 mois "
                f"({days} jours calendaires)."
            )
    else:
        if seniority_months < 24:
            days = _months_to_days(1)
            detail = (
                "Non-cadre, ancienneté de 6 mois à moins de 2 ans : préavis légal de 1 mois "
                f"({days} jours calendaires)."
            )
        else:
            days = _months_to_days(2)
            detail = (
                "Non-cadre, ancienneté d'au moins 2 ans : préavis légal de 2 mois "
                f"({days} jours calendaires)."
            )

    exit_label = "démission" if exit_type == "demission" else "licenciement"
    return NoticePeriodResult(
        days=days,
        source="legal",
        label=f"{days} jours",
        detail=f"Préavis légal pour une {exit_label} — {detail}",
        seniority_months=seniority_months,
        employee_category=category,
    )


def _match_palier(
    paliers: List[Dict[str, Any]], seniority_months: int
) -> Optional[int]:
    for palier in paliers:
        if not isinstance(palier, dict):
            continue
        mois_min = palier.get("anciennete_mois_min", palier.get("mois_min", 0))
        mois_max = palier.get("anciennete_mois_max", palier.get("mois_max"))
        try:
            mois_min_i = int(mois_min) if mois_min is not None else 0
        except (TypeError, ValueError):
            mois_min_i = 0
        if seniority_months < mois_min_i:
            continue
        if mois_max is not None:
            try:
                mois_max_i = int(mois_max)
            except (TypeError, ValueError):
                mois_max_i = None
            if mois_max_i is not None and seniority_months >= mois_max_i:
                continue
        jours = palier.get("jours", palier.get("days"))
        if jours is None:
            mois = palier.get("mois", palier.get("months"))
            if mois is not None:
                try:
                    return _months_to_days(int(mois))
                except (TypeError, ValueError):
                    return None
            return None
        try:
            return max(0, int(jours))
        except (TypeError, ValueError):
            return None
    return None


def _convention_notice_days(
    rules: Dict[str, Any],
    exit_type: str,
    *,
    category: EmployeeCategory,
    seniority_months: int,
) -> Optional[int]:
    preavis = rules.get("preavis")
    if not isinstance(preavis, dict):
        return None

    exit_key_map = {
        "demission": ("demission", "demission_salarie", "salarie"),
        "licenciement": ("licenciement", "licenciement_employeur", "employeur"),
    }
    keys = exit_key_map.get(exit_type)
    if not keys:
        return None

    section: Any = None
    for key in keys:
        if key in preavis:
            section = preavis[key]
            break
    if section is None:
        section = preavis.get("commun") or preavis.get("default")
    if section is None:
        return None

    if isinstance(section, list):
        return _match_palier(section, seniority_months)

    if not isinstance(section, dict):
        return None

    cat_key = "cadre" if category == "cadre" else "non_cadre"
    paliers = section.get(cat_key) or section.get("tous") or section.get("all")
    if isinstance(paliers, list):
        return _match_palier(paliers, seniority_months)
    if isinstance(paliers, dict):
        return _match_palier([paliers], seniority_months)
    return None


def compute_notice_period(
    *,
    exit_type: str,
    hire_date: Optional[date],
    reference_date: date,
    statut: Any = None,
    is_gross_misconduct: bool = False,
    collective_agreement_name: Optional[str] = None,
    collective_agreement_idcc: Optional[str] = None,
    cc_rules: Optional[Dict[str, Any]] = None,
) -> NoticePeriodResult:
    """
    Calcule le préavis applicable pour un départ.

    collective_agreement_name/idcc : convention effective (employé ou entreprise).
    cc_rules : document JSON des règles CC (convention_collective_rules.rules).
    """
    category, statut_explicit = resolve_employee_category(statut)
    warnings: List[str] = []

    if not statut_explicit:
        warnings.append(
            "Statut cadre / non-cadre non renseigné : calcul basé sur les minima non-cadre."
        )

    if hire_date is None:
        legal = _legal_notice_days(
            exit_type,
            category=category,
            seniority_months=0,
            is_gross_misconduct=is_gross_misconduct,
        )
        return NoticePeriodResult(
            days=legal.days,
            source=legal.source,
            label=legal.label,
            detail=legal.detail,
            warnings=tuple(
                [
                    "Date d'embauche non renseignée : l'ancienneté et le préavis ne peuvent pas être calculés précisément.",
                ]
                + list(warnings)
                + list(legal.warnings)
            ),
            collective_agreement_name=collective_agreement_name,
            collective_agreement_idcc=_normalize_idcc(collective_agreement_idcc),
            employee_category=category,
            applicable=legal.applicable,
        )

    seniority_months = compute_seniority_months(hire_date, reference_date)

    if cc_rules:
        conv_days = _convention_notice_days(
            cc_rules,
            exit_type,
            category=category,
            seniority_months=seniority_months,
        )
        if conv_days is not None:
            cc_label = collective_agreement_name or "Convention collective"
            idcc = _normalize_idcc(collective_agreement_idcc)
            idcc_part = f" (IDCC {idcc})" if idcc else ""
            return NoticePeriodResult(
                days=conv_days,
                source="convention",
                label=f"{conv_days} jours",
                detail=(
                    f"Préavis conventionnel selon {cc_label}{idcc_part} "
                    f"pour une ancienneté de {seniority_months} mois."
                ),
                warnings=tuple(warnings),
                collective_agreement_name=collective_agreement_name,
                collective_agreement_idcc=idcc,
                seniority_months=seniority_months,
                employee_category=category,
            )
        if collective_agreement_name or collective_agreement_idcc:
            warnings.append(
                "Aucune règle de préavis extraite pour cette convention — préavis légal appliqué."
            )
    elif not collective_agreement_name and not collective_agreement_idcc:
        warnings.append(
            "Aucune convention collective assignée à ce collaborateur — préavis légal appliqué."
        )

    legal = _legal_notice_days(
        exit_type,
        category=category,
        seniority_months=seniority_months,
        is_gross_misconduct=is_gross_misconduct,
    )
    return NoticePeriodResult(
        days=legal.days,
        source=legal.source,
        label=legal.label,
        detail=legal.detail,
        warnings=tuple(list(warnings) + list(legal.warnings)),
        collective_agreement_name=collective_agreement_name,
        collective_agreement_idcc=_normalize_idcc(collective_agreement_idcc),
        seniority_months=seniority_months,
        employee_category=category,
        applicable=legal.applicable,
    )

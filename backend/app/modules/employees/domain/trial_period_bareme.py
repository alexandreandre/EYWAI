"""Barème de période d'essai : proposition par type de contrat et statut.

Le barème propose, il n'impose pas — la durée reste modifiable salarié par
salarié. Les valeurs par défaut sont les durées légales (L1221-19 pour le CDI,
L1242-10 pour le CDD). La base ne distinguant que Cadre et Non-Cadre, la
maîtrise — trois mois en droit — n'a pas de ligne propre et s'ajuste à la main.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from app.modules.employees.domain.trial_period_dates import (
    UNIT_DAYS,
    UNIT_MONTHS,
    VALID_UNITS,
)

DEFAULT_ALERT_DAYS = 15

DEFAULT_BAREME: Tuple[Dict[str, Any], ...] = (
    {
        "contract_type": "CDI",
        "statut": "Non-Cadre",
        "duree": 2,
        "unite": UNIT_MONTHS,
        "renouvellement": True,
    },
    {
        "contract_type": "CDI",
        "statut": "Cadre",
        "duree": 4,
        "unite": UNIT_MONTHS,
        "renouvellement": True,
    },
    {
        "contract_type": "CDD",
        "statut": "Non-Cadre",
        "duree": 1,
        "unite": UNIT_MONTHS,
        "renouvellement": False,
    },
    {
        "contract_type": "CDD",
        "statut": "Cadre",
        "duree": 1,
        "unite": UNIT_MONTHS,
        "renouvellement": False,
    },
)

DEFAULT_EXCLUDED_CONTRACTS = frozenset(
    {"apprentissage", "professionnalisation", "stage", "convention de stage"}
)

# Un CDD de six mois ou moins ouvre un jour d'essai par semaine de contrat,
# plafonné à deux semaines (L1242-10).
CDD_SHORT_THRESHOLD_MONTHS = 6
CDD_SHORT_CAP_DAYS = 14
WEEKS_PER_MONTH = 4.348


@dataclass(frozen=True)
class TrialProposal:
    duration_value: int
    duration_unit: str
    renewal_allowed: bool


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _section(company_settings: Any) -> Dict[str, Any]:
    if not isinstance(company_settings, dict):
        return {}
    section = company_settings.get("periode_essai")
    return section if isinstance(section, dict) else {}


def resolve_alert_days(company_settings: Any) -> int:
    raw = _section(company_settings).get("alerte_jours")
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_ALERT_DAYS
    return days if days > 0 else DEFAULT_ALERT_DAYS


def _is_excluded(section: Dict[str, Any], contract_type: str) -> bool:
    raw = section.get("exclusions")
    if isinstance(raw, (list, tuple)):
        excluded = {_norm(x) for x in raw}
    else:
        excluded = set(DEFAULT_EXCLUDED_CONTRACTS)
    return _norm(contract_type) in excluded


def _cdd_proposal(contract_duration_months: Optional[float]) -> TrialProposal:
    if (
        contract_duration_months is None
        or contract_duration_months > CDD_SHORT_THRESHOLD_MONTHS
    ):
        return TrialProposal(1, UNIT_MONTHS, False)
    weeks = int(contract_duration_months * WEEKS_PER_MONTH)
    days = max(1, min(weeks, CDD_SHORT_CAP_DAYS))
    return TrialProposal(days, UNIT_DAYS, False)


def _find_line(
    section: Dict[str, Any],
    contract_type: str,
    statut: str,
) -> Optional[Dict[str, Any]]:
    custom = section.get("bareme")
    lines = list(custom) if isinstance(custom, (list, tuple)) else []
    lines.extend(DEFAULT_BAREME)
    for line in lines:
        if not isinstance(line, dict):
            continue
        if _norm(line.get("contract_type")) != _norm(contract_type):
            continue
        if _norm(line.get("statut")) != _norm(statut):
            continue
        return line
    return None


def resolve_trial_proposal(
    company_settings: Any,
    contract_type: str,
    statut: str,
    contract_duration_months: Optional[float] = None,
) -> Optional[TrialProposal]:
    """Période d'essai proposée, ou None si le contrat n'en ouvre pas."""
    section = _section(company_settings)

    if _is_excluded(section, contract_type):
        return None

    line = _find_line(section, contract_type, statut)
    if line is None:
        return None

    # La règle légale CDD prime sur la ligne de barème, sauf si la société l'a
    # explicitement désactivée pour saisir une durée fixe.
    if _norm(contract_type) == "cdd" and section.get("regle_legale_cdd", True):
        return _cdd_proposal(contract_duration_months)

    try:
        duree = int(line.get("duree"))
    except (TypeError, ValueError):
        return None
    if duree <= 0:
        return None

    return TrialProposal(
        duration_value=duree,
        duration_unit=str(line.get("unite") or UNIT_MONTHS),
        renewal_allowed=bool(line.get("renouvellement", False)),
    )


def validate_trial_period_settings(section: Any) -> Dict[str, Any]:
    """Nettoie le barème saisi par un RH avant de l'enregistrer.

    Une durée nulle ou une unité inconnue rendrait le calcul de fin muet et la
    période invisible : mieux vaut refuser la saisie que produire un suivi qui
    ne se déclenche jamais.
    """
    if not isinstance(section, dict):
        return {}

    out: Dict[str, Any] = {}

    if "alerte_jours" in section:
        try:
            days = int(section["alerte_jours"])
        except (TypeError, ValueError):
            raise ValueError("délai d'alerte invalide") from None
        if days <= 0:
            raise ValueError("délai d'alerte invalide : il doit être positif")
        out["alerte_jours"] = days

    if "regle_legale_cdd" in section:
        out["regle_legale_cdd"] = bool(section["regle_legale_cdd"])

    if "exclusions" in section:
        raw = section["exclusions"]
        if not isinstance(raw, (list, tuple)):
            raise ValueError("exclusions invalides : une liste est attendue")
        out["exclusions"] = [str(x).strip() for x in raw if str(x).strip()]

    if "bareme" in section:
        raw = section["bareme"]
        if not isinstance(raw, (list, tuple)):
            raise ValueError("barème invalide : une liste est attendue")
        lines = []
        for line in raw:
            if not isinstance(line, dict):
                raise ValueError("barème invalide : chaque ligne est un objet")
            contract_type = str(line.get("contract_type") or "").strip()
            if not contract_type:
                raise ValueError("ligne de barème sans type de contrat")
            statut = str(line.get("statut") or "").strip()
            if not statut:
                raise ValueError("ligne de barème sans statut")
            try:
                duree = int(line.get("duree"))
            except (TypeError, ValueError):
                raise ValueError("durée de barème invalide") from None
            if duree <= 0:
                raise ValueError("durée de barème invalide : elle doit être positive")
            unite = str(line.get("unite") or "").strip().lower()
            if unite not in VALID_UNITS:
                raise ValueError(
                    "unité de barème invalide : jours, semaines ou mois attendus"
                )
            lines.append(
                {
                    "contract_type": contract_type,
                    "statut": statut,
                    "duree": duree,
                    "unite": unite,
                    "renouvellement": bool(line.get("renouvellement", False)),
                }
            )
        out["bareme"] = lines

    return out


__all__ = [
    "DEFAULT_ALERT_DAYS",
    "DEFAULT_BAREME",
    "DEFAULT_EXCLUDED_CONTRACTS",
    "TrialProposal",
    "resolve_alert_days",
    "resolve_trial_proposal",
    "validate_trial_period_settings",
]

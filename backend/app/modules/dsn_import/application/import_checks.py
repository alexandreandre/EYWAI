"""Contrôles contextuels import DSN (période, entreprise cible)."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from app.modules.dsn_import.domain.user_messages import target_siret_missing_anomaly
from app.modules.dsn_import.infrastructure import repository as repo

IMPORT_WARNING_TYPES = frozenset(
    {
        "period_mismatch",
        "intended_period_mismatch",
        "company_name_mismatch",
        "siret_mismatch",
        "target_siret_missing",
    }
)

ENRICHMENT_WARNING_TYPES = frozenset(
    {
        "employee_other_company",
        "psc_warning",
        "parse_warning",
        "workforce_reconciliation_required",
        "employee_missing_from_dsn",
        "employee_new_hire_not_in_dsn",
        "employee_contract_end_in_dsn",
        "workforce_active_without_nir",
    }
)

_MONTHS_FR = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]

_LEGAL_SUFFIXES = (
    " sas",
    " sarl",
    " sa",
    " eurl",
    " scop",
    " sca",
    " scs",
    " snc",
    " selarl",
    " selas",
)

_STOP_TOKENS = frozenset({"de", "du", "la", "le", "les", "et", "en", "au", "aux", "the"})


def format_period_fr(period: str) -> str:
    try:
        y, m = period.split("-")
        mi = int(m)
        if 1 <= mi <= 12:
            return f"{_MONTHS_FR[mi - 1]} {y}"
    except (ValueError, IndexError):
        pass
    return period


def normalize_company_name(name: str) -> str:
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", str(name))
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    for suffix in _LEGAL_SUFFIXES:
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def _significant_tokens(name: str) -> set[str]:
    return {
        t
        for t in normalize_company_name(name).split()
        if len(t) > 2 and t not in _STOP_TOKENS
    }


def company_names_semantically_match(a: str, b: str) -> bool:
    """Compare deux raisons sociales (tolérant casse, forme juridique, tokens)."""
    if not a or not b:
        return True
    na = normalize_company_name(a)
    nb = normalize_company_name(b)
    if not na or not nb:
        return True
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    if SequenceMatcher(None, na, nb).ratio() >= 0.82:
        return True
    ta, tb = _significant_tokens(a), _significant_tokens(b)
    if not ta or not tb:
        return False
    smaller, larger = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if not smaller:
        return False
    overlap = sum(1 for t in smaller if t in larger)
    return overlap / len(smaller) >= 0.75


def normalize_siret(value: Optional[str]) -> str:
    return re.sub(r"\s", "", str(value or ""))


def sirets_match(a: Optional[str], b: Optional[str]) -> bool:
    if not a or not b:
        return True
    return normalize_siret(a) == normalize_siret(b)


def _warning(
    *,
    type_: str,
    message: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "type": type_,
        "message": message,
        "severity": "warning",
        "source_ref": None,
        "meta": meta or {},
    }


def strip_import_context_warnings(anomalies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [a for a in anomalies if a.get("type") not in IMPORT_WARNING_TYPES]


def strip_enrichment_warnings(anomalies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        a
        for a in anomalies
        if a.get("type") not in ENRICHMENT_WARNING_TYPES
        and a.get("code") not in ENRICHMENT_WARNING_TYPES
    ]


def attach_import_context_warnings(
    anomalies: List[Dict[str, Any]],
    summary: Dict[str, Any],
    *,
    mode: str,
    target_company_id: Optional[str],
    periods: List[str],
    dsn_company_name: Optional[str] = None,
    intended_period: Optional[str] = None,
) -> None:
    """Ajoute avertissements période / entreprise (non bloquants, confirmables côté UI)."""
    summary.pop("period_mismatch", None)
    summary.pop("intended_period_mismatch", None)
    summary.pop("company_name_mismatch", None)
    summary.pop("siret_mismatch", None)
    summary.pop("detected_period", None)
    summary.pop("expected_import_period", None)
    summary.pop("next_import_period", None)

    if mode != "monthly" or not target_company_id:
        return

    company = repo.find_company_by_id(target_company_id)
    if not company:
        return

    detected = _primary_detected_period(summary, periods)
    if detected:
        summary["detected_period"] = detected

    from app.modules.dsn_import.application.coverage import (
        compute_coverage,
        resolve_next_import_period,
    )

    cov = compute_coverage(company)
    expected = cov.get("expected_last_period")
    next_import = resolve_next_import_period(cov)
    months_covered = set(cov.get("months_covered") or [])
    if expected:
        summary["expected_import_period"] = expected
    if next_import:
        summary["next_import_period"] = next_import

    reference_period = intended_period or next_import
    if detected and reference_period and detected != reference_period:
        explicit_reimport = (
            bool(intended_period)
            and intended_period == detected
            and detected in months_covered
        )
        if not explicit_reimport:
            summary["period_mismatch"] = {
                "expected": reference_period,
                "detected": detected,
                "next_import_period": next_import,
            }
            anomalies.append(
                _warning(
                    type_="period_mismatch",
                    message=(
                        f"La DSN concerne {format_period_fr(detected)}, "
                        f"alors que le prochain mois à importer est "
                        f"{format_period_fr(reference_period)}. "
                        f"Confirmez pour importer {format_period_fr(detected)} quand même."
                    ),
                    meta={
                        "expected": reference_period,
                        "detected": detected,
                        "next_import_period": next_import,
                    },
                )
            )

    if intended_period and detected and intended_period != detected:
        summary["intended_period_mismatch"] = {
            "intended": intended_period,
            "detected": detected,
        }
        anomalies.append(
            _warning(
                type_="intended_period_mismatch",
                message=(
                    f"Vous visiez {format_period_fr(intended_period)} "
                    f"mais le fichier DSN correspond à {format_period_fr(detected)}. "
                    f"Confirmez pour importer {format_period_fr(detected)}."
                ),
                meta={"intended": intended_period, "detected": detected},
            )
        )

    dsn_name = (dsn_company_name or summary.get("dsn_company_name") or "").strip()
    target_name = (company.get("company_name") or company.get("raison_sociale") or "").strip()
    if dsn_name and target_name and not company_names_semantically_match(dsn_name, target_name):
        summary["company_name_mismatch"] = {
            "dsn_name": dsn_name,
            "target_name": target_name,
        }
        anomalies.append(
            _warning(
                type_="company_name_mismatch",
                message=(
                    f"La raison sociale dans la DSN (« {dsn_name} ») ne correspond pas "
                    f"clairement à l'entreprise sélectionnée (« {target_name} »). "
                    "Confirmez qu'il s'agit bien du bon dossier."
                ),
                meta={"dsn_name": dsn_name, "target_name": target_name},
            )
        )

    dsn_siret = summary.get("siret")
    target_siret = company.get("siret")
    if dsn_siret and target_siret and not sirets_match(str(dsn_siret), str(target_siret)):
        summary["siret_mismatch"] = {
            "dsn_siret": normalize_siret(str(dsn_siret)),
            "target_siret": normalize_siret(str(target_siret)),
        }
        anomalies.append(
            _warning(
                type_="siret_mismatch",
                message=(
                    f"Le SIRET de la DSN ({normalize_siret(str(dsn_siret))}) "
                    f"diffère de celui de l'entreprise cible "
                    f"({normalize_siret(str(target_siret))}). "
                    "Confirmez le rattachement."
                ),
                meta=summary["siret_mismatch"],
            )
        )
    elif dsn_siret and not target_siret:
        summary["target_siret_missing"] = {
            "dsn_siret": normalize_siret(str(dsn_siret)),
            "target_name": target_name,
        }
        anomalies.append(
            target_siret_missing_anomaly(
                target_company_name=target_name or "l'entreprise sélectionnée",
                dsn_siret=normalize_siret(str(dsn_siret)),
            )
        )


def _primary_detected_period(summary: Dict[str, Any], periods: List[str]) -> Optional[str]:
    if len(periods) == 1:
        return periods[0]
    pmin = summary.get("period_min")
    pmax = summary.get("period_max")
    if pmin and pmax and pmin == pmax:
        return str(pmin)
    if periods:
        return periods[0]
    return str(pmin) if pmin else None

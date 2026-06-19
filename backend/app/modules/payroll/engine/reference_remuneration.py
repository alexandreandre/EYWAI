"""Lecture de la rémunération brute de référence pour l'ICCP (règle du 1/10e)."""

from __future__ import annotations

import json
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from app.modules.absences.domain.rules import get_cp_reference_period
from app.modules.payroll.engine.iccp_arbitrage import lire_parametres_conges


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_cp_reference_period_bounds(
    ref_date: date, *, start_month: int = 6
) -> tuple[date, date]:
    return get_cp_reference_period(ref_date, start_month=start_month)


def _iter_months_in_period(period_start: date, period_end: date) -> list[tuple[int, int]]:
    months: list[tuple[int, int]] = []
    year, month = period_start.year, period_start.month
    while (year, month) <= (period_end.year, period_end.month):
        months.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def _format_periode(period_start: date, period_end: date) -> str:
    return (
        f"{period_start.strftime('%d/%m/%Y')} – {period_end.strftime('%d/%m/%Y')}"
    )


@dataclass
class ReferenceRemunerationResult:
    base_totale: float
    periode_debut: date
    periode_fin: date
    periode_label: str
    mois_avec_bulletin: int = 0
    mois_total: int = 0
    prime_precarite_incluse: float = 0.0
    alertes: list[str] = field(default_factory=list)
    source: str = "payslips"


def lire_brut_payslip(payslip_data: dict | None) -> float:
    if not payslip_data:
        return 0.0
    return _safe_float(payslip_data.get("salaire_brut", 0))


def lire_bruts_periode_reference(
    employee_id: str,
    ref_date: date,
    supabase_client: Any,
    *,
    start_month: int = 6,
    salaire_contractuel_fallback: float = 0.0,
) -> ReferenceRemunerationResult:
    period_start, period_end = get_cp_reference_period_bounds(
        ref_date, start_month=start_month
    )
    months = _iter_months_in_period(period_start, period_end)
    total_brut = 0.0
    mois_avec_bulletin = 0
    alertes: list[str] = []

    for year, month in months:
        try:
            resp = (
                supabase_client.table("payslips")
                .select("payslip_data")
                .match({"employee_id": employee_id, "year": year, "month": month})
                .maybe_single()
                .execute()
            )
            row = resp.data if resp and hasattr(resp, "data") else None
        except Exception:
            row = None

        if row and row.get("payslip_data"):
            brut = lire_brut_payslip(row["payslip_data"])
            if brut > 0:
                mois_avec_bulletin += 1
            total_brut += brut
        elif salaire_contractuel_fallback > 0:
            total_brut += salaire_contractuel_fallback
            alertes.append(
                f"Bulletin {month:02d}/{year} absent — salaire contractuel utilisé."
            )
        else:
            alertes.append(f"Bulletin {month:02d}/{year} absent — mois ignoré.")

    if mois_avec_bulletin == 0 and salaire_contractuel_fallback > 0:
        alertes.append(
            "Aucun bulletin sur la période de référence — estimation sur salaire contractuel."
        )

    return ReferenceRemunerationResult(
        base_totale=round(total_brut, 2),
        periode_debut=period_start,
        periode_fin=period_end,
        periode_label=_format_periode(period_start, period_end),
        mois_avec_bulletin=mois_avec_bulletin,
        mois_total=len(months),
        alertes=alertes,
        source="payslips",
    )


def lire_bruts_depuis_cumuls(
    employee_path: Path,
    period_start: date,
    period_end: date,
) -> ReferenceRemunerationResult:
    cumuls_dir = employee_path / "cumuls"
    total = 0.0
    mois_comptes = 0
    prev_brut_total: float | None = None

    for year, month in _iter_months_in_period(period_start, period_end):
        fichier = cumuls_dir / f"{month:02d}.json"
        if not fichier.exists():
            continue
        try:
            data = json.loads(fichier.read_text(encoding="utf-8"))
            brut_total = _safe_float(data.get("cumuls", {}).get("brut_total", 0))
        except (json.JSONDecodeError, OSError):
            continue
        if prev_brut_total is not None:
            delta = brut_total - prev_brut_total
            if delta > 0:
                total += delta
                mois_comptes += 1
        prev_brut_total = brut_total

    alertes: list[str] = []
    if mois_comptes == 0:
        alertes.append("Cumuls disque insuffisants pour la période de référence.")

    return ReferenceRemunerationResult(
        base_totale=round(total, 2),
        periode_debut=period_start,
        periode_fin=period_end,
        periode_label=_format_periode(period_start, period_end),
        mois_avec_bulletin=mois_comptes,
        mois_total=len(_iter_months_in_period(period_start, period_end)),
        alertes=alertes,
        source="cumuls",
    )


def lire_brut_total_contrat(
    employee_id: str,
    date_debut: date,
    date_fin: date,
    supabase_client: Any,
    *,
    salaire_contractuel_fallback: float = 0.0,
) -> tuple[float, list[str]]:
    """Somme des bruts bulletin sur la durée du contrat (embauche → sortie)."""
    months = _iter_months_in_period(date_debut, date_fin)
    total_brut = 0.0
    mois_avec_bulletin = 0
    alertes: list[str] = []

    for year, month in months:
        try:
            resp = (
                supabase_client.table("payslips")
                .select("payslip_data")
                .match({"employee_id": employee_id, "year": year, "month": month})
                .maybe_single()
                .execute()
            )
            row = resp.data if resp and hasattr(resp, "data") else None
        except Exception:
            row = None

        if row and row.get("payslip_data"):
            brut = lire_brut_payslip(row["payslip_data"])
            if brut > 0:
                mois_avec_bulletin += 1
                total_brut += brut
        elif salaire_contractuel_fallback > 0:
            total_brut += salaire_contractuel_fallback

    if mois_avec_bulletin == 0 and salaire_contractuel_fallback > 0:
        alertes.append(
            "Aucun bulletin sur le contrat — estimation sur salaire contractuel."
        )

    return round(total_brut, 2), alertes


def estimer_extras_fin_contrat(
    brut_total_contrat: float,
    baremes: dict | None,
    *,
    is_cdd: bool = False,
    is_interim: bool = False,
    specificites: dict | None = None,
) -> tuple[float, float]:
    """Estime prime de précarité (CDD) et IFM (intérim), aligné sur calcul_brut."""
    if brut_total_contrat <= 0:
        return 0.0, 0.0

    spec = specificites or {}
    baremes = baremes or {}
    montant_precarite = 0.0
    montant_ifm = 0.0

    if is_cdd and not spec.get("exclure_prime_precarite") and not spec.get(
        "cdd_sans_precarite"
    ):
        prec_cfg = (baremes.get("cdd", {}) or {}).get("precarite", {}) or {}
        if prec_cfg.get("actif") is not False:
            taux = float(prec_cfg.get("taux", 0.10))
            montant_precarite = round(brut_total_contrat * taux, 2)

    if is_interim and not spec.get("exclure_ifm"):
        ifm_cfg = (baremes.get("interim", {}) or {}).get("ifm", {}) or {}
        if ifm_cfg.get("actif") is not False:
            taux = float(ifm_cfg.get("taux", 0.10))
            montant_ifm = round(brut_total_contrat * taux, 2)

    return montant_precarite, montant_ifm


def ajouter_prime_precarite_si_cdd(
    base: float,
    *,
    is_cdd: bool,
    montant_precarite: float = 0.0,
    montant_ifm: float = 0.0,
) -> tuple[float, float]:
    extra = 0.0
    if is_cdd and montant_precarite > 0:
        extra += montant_precarite
    if montant_ifm > 0:
        extra += montant_ifm
    return round(base + extra, 2), round(extra, 2)


def calculer_base_reference_dixieme(
    employee_id: str,
    ref_date: date,
    supabase_client: Any,
    *,
    start_month: int = 6,
    salaire_contractuel_fallback: float = 0.0,
    employee_path: Path | None = None,
    is_cdd: bool = False,
    montant_precarite: float = 0.0,
    montant_ifm: float = 0.0,
) -> ReferenceRemunerationResult:
    ref = lire_bruts_periode_reference(
        employee_id,
        ref_date,
        supabase_client,
        start_month=start_month,
        salaire_contractuel_fallback=salaire_contractuel_fallback,
    )

    if ref.base_totale <= 0 and employee_path is not None:
        period_start, period_end = get_cp_reference_period_bounds(
            ref_date, start_month=start_month
        )
        ref_cumuls = lire_bruts_depuis_cumuls(employee_path, period_start, period_end)
        if ref_cumuls.base_totale > 0:
            ref = ref_cumuls

    base_avec_extras, extras = ajouter_prime_precarite_si_cdd(
        ref.base_totale,
        is_cdd=is_cdd,
        montant_precarite=montant_precarite,
        montant_ifm=montant_ifm,
    )
    ref.base_totale = base_avec_extras
    ref.prime_precarite_incluse = extras
    return ref


def calculer_iccp_l1243_8(
    brut_total_contrat: float,
    *,
    montant_precarite: float = 0.0,
    montant_ifm: float = 0.0,
    taux: float = 0.10,
) -> float:
    base = brut_total_contrat + max(montant_precarite, 0.0) + max(montant_ifm, 0.0)
    return round(base * taux, 2) if base > 0 else 0.0


def mettre_a_jour_brut_reference_cumul(
    cumuls_data: dict,
    brut_mois: float,
    ref_date: date,
    *,
    start_month: int = 6,
) -> dict:
    """Met à jour brut_reference_n_1 (somme des bruts de la période CP en cours)."""
    period_start, period_end = get_cp_reference_period_bounds(
        ref_date, start_month=start_month
    )
    cumuls = cumuls_data.setdefault("cumuls", {})
    stored_start = cumuls.get("brut_reference_period_start")
    stored_end = cumuls.get("brut_reference_period_end")

    if (
        stored_start != period_start.isoformat()
        or stored_end != period_end.isoformat()
    ):
        cumuls["brut_reference_n_1"] = round(brut_mois, 2)
        cumuls["brut_reference_period_start"] = period_start.isoformat()
        cumuls["brut_reference_period_end"] = period_end.isoformat()
    else:
        cumuls["brut_reference_n_1"] = round(
            float(cumuls.get("brut_reference_n_1", 0.0)) + brut_mois, 2
        )

    return cumuls_data


def lire_brut_reference_depuis_cumuls(cumuls_data: dict | None) -> float:
    if not isinstance(cumuls_data, dict):
        return 0.0
    nested = cumuls_data.get("cumuls", cumuls_data)
    if not isinstance(nested, dict):
        return 0.0
    return _safe_float(nested.get("brut_reference_n_1", 0.0))


def lire_parametres_depuis_baremes(baremes: dict | None) -> dict[str, float]:
    return lire_parametres_conges(baremes)

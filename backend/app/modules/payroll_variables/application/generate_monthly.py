"""Génération mensuelle variables paie."""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from typing import Any

from app.core.database import supabase
from app.modules.payroll.engine.baremes_loader import assembler_baremes, charger_db_baremes
from app.modules.payroll_variables.domain.astreinte_km import (
    evaluate_astreinte_weekend_km,
    read_deplacement_astreinte,
)
from app.modules.payroll_variables.domain.astreinte_week import (
    evaluate_astreinte_week_tiered,
)
from app.modules.payroll_variables.domain.astreinte_weekend_majoration import (
    evaluate_astreinte_weekend_majoration,
)
from app.modules.payroll_variables.domain.hourly_rate import resolve_hourly_rate
from app.modules.payroll_variables.domain.rules import (
    compute_rule_amount,
    employee_matches_conditions,
)
from app.modules.payroll_variables.domain.presence_week import evaluate_presence_weeks
from app.modules.payroll_variables.domain.transport_allowance import (
    est_absent_tout_le_mois,
    montant_transport_mensuel,
)
from app.modules.payroll_variables.infrastructure.absence_queries import (
    list_locked_shift_dates_for_employee,
    list_validated_absences_for_employees_in_range,
)
from app.modules.payroll_variables.infrastructure import repository as repo


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    _, last = calendar.monthrange(year, month)
    return date(year, month, 1), date(year, month, last)


def _slug_prime_id(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return slug or "prime"


def _count_astreinte_weeks(employee_id: str, start: date, end: date) -> int:
    dates = _astreinte_shift_dates(employee_id, start, end)
    weeks: set[str] = set()
    for d in dates:
        monday = d - timedelta(days=d.weekday())
        weeks.add(monday.isoformat())
    return len(weeks)


def _astreinte_shift_dates(employee_id: str, start: date, end: date) -> list[date]:
    resp = (
        supabase.table("shifts")
        .select("shift_date")
        .eq("employee_id", employee_id)
        .in_("transverse_category", ["astreinte", "on_call"])
        .gte("shift_date", start.isoformat())
        .lte("shift_date", end.isoformat())
        .execute()
    )
    dates: list[date] = []
    for row in resp.data or []:
        d_raw = row.get("shift_date")
        if not d_raw:
            continue
        dates.append(date.fromisoformat(str(d_raw)[:10]))
    return dates


def _parse_date_iso(valeur: Any) -> date | None:
    """Parse une date ISO issue de la base ; None si absente ou invalide."""
    if not valeur:
        return None
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10])
    except ValueError:
        return None


def _jours_absence(rows: list[dict[str, Any]], start: date, end: date) -> set[date]:
    """Jours couverts par les absences validées, bornés au mois.

    Les absences sont stockées comme une liste de jours explicites
    (`absence_requests.selected_days`), pas comme un intervalle début/fin.
    """
    jours: set[date] = set()
    for row in rows:
        for raw in row.get("selected_days") or []:
            jour = _parse_date_iso(raw)
            if jour and start <= jour <= end:
                jours.add(jour)
    return jours


def _load_calendrier_reel(employee_id: str, year: int, month: int) -> list[dict[str, Any]]:
    resp = (
        supabase.table("employee_schedules")
        .select("actual_hours")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return []
    actual = rows[0].get("actual_hours") or {}
    if not isinstance(actual, dict):
        return []
    cal = actual.get("calendrier_reel") or []
    return cal if isinstance(cal, list) else []


def _load_manual_trips(
    employee_id: str, year: int, month: int, input_name: str | None
) -> float:
    if not input_name:
        return 0.0
    resp = (
        supabase.table("monthly_inputs")
        .select("amount")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .eq("name", input_name)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return 0.0
    return float(rows[0].get("amount") or 0)


def _fetch_baremes_km() -> dict[str, Any]:
    db = charger_db_baremes(supabase)
    assembled = assembler_baremes(db)
    km = assembled.get("baremes_km") or {}
    return km if isinstance(km, dict) else {}


def _shift_payroll_summary(employee_id: str, year: int, month: int) -> dict[str, Any]:
    resp = (
        supabase.table("employee_schedules")
        .select("payroll_events")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return {}
    events = rows[0].get("payroll_events") or {}
    if not isinstance(events, dict):
        return {}
    summary = events.get("shift_payroll_summary") or {}
    return summary if isinstance(summary, dict) else {}


def _modulation_balance_hours(
    employee_id: str, company_id: str, year: int
) -> float:
    resp = (
        supabase.table("employee_modulation_counters")
        .select("balance_hours")
        .eq("employee_id", employee_id)
        .eq("company_id", company_id)
        .eq("year", year)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if rows:
        return float(rows[0].get("balance_hours") or 0)
    return 0.0


def _count_planning_shift_entries(
    employee_id: str,
    year: int,
    month: int,
    shift_type_codes: list[str] | None,
) -> float:
    resp = (
        supabase.table("employee_schedules")
        .select("payroll_events")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return 0.0
    events = rows[0].get("payroll_events") or {}
    if not isinstance(events, dict):
        return 0.0
    planning_hours = events.get("planning_hours") or []
    if not isinstance(planning_hours, list):
        return 0.0
    codes = {c.lower() for c in (shift_type_codes or [])}
    count = 0.0
    for entry in planning_hours:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("shift_type_code") or "").lower()
        if not codes or code in codes:
            count += 1.0
    return count


def _count_shift_type_occurrences(
    employee_id: str,
    year: int,
    month: int,
    shift_type_codes: list[str] | None,
) -> float:
    start, end = _month_bounds(year, month)
    resp = (
        supabase.table("shifts")
        .select("shift_date, shift_types(code)")
        .eq("employee_id", employee_id)
        .eq("is_locked", True)
        .is_("transverse_category", "null")
        .gte("shift_date", start.isoformat())
        .lte("shift_date", end.isoformat())
        .execute()
    )
    count = 0.0
    codes = {c.lower() for c in (shift_type_codes or [])}
    for row in resp.data or []:
        st = row.get("shift_types") if isinstance(row.get("shift_types"), dict) else {}
        code = str(st.get("code") or "").lower()
        if not codes or code in codes:
            count += 1.0
    if count > 0:
        return count
    return _count_planning_shift_entries(employee_id, year, month, shift_type_codes)


def _resolve_quantity(
    rule: dict[str, Any],
    employee_id: str,
    company_id: str,
    year: int,
    month: int,
) -> float:
    rule_type = rule.get("rule_type") or ""
    start, end = _month_bounds(year, month)
    if rule_type == "per_astreinte_week":
        return float(_count_astreinte_weeks(employee_id, start, end))
    if rule_type == "per_modulation_payout":
        return max(0.0, _modulation_balance_hours(employee_id, company_id, year))
    if rule_type == "per_night_hour":
        summary = _shift_payroll_summary(employee_id, year, month)
        night = float(summary.get("night_hours") or 0)
        if night > 0:
            return night
        from app.modules.planning.application.shift_payroll_aggregation import (
            aggregate_shift_payroll_metrics,
        )

        live = aggregate_shift_payroll_metrics(
            employee_id, year, month, company_id=company_id
        )
        return float(live.get("night_hours") or 0)
    if rule_type == "per_shift_type":
        shift_codes = (rule.get("conditions") or {}).get("shift_type_codes")
        codes = [str(c) for c in shift_codes] if isinstance(shift_codes, list) else None
        return _count_shift_type_occurrences(employee_id, year, month, codes)
    if rule_type == "per_week_without_absence":
        return 0.0
    return 1.0


def _bonus_type_meta(
    rule: dict[str, Any],
) -> tuple[str, bool, bool, str | None, str | None, str | None]:
    """Retourne label, is_socially_taxed, is_taxable, catalog_prime_id,
    export_code, situation_repas."""
    conditions = rule.get("conditions") or {}
    catalog_from_rule = conditions.get("catalog_prime_id")
    catalog_id = str(catalog_from_rule) if catalog_from_rule else None
    export_code: str | None = None
    cond_export = conditions.get("export_code")
    if cond_export:
        export_code = str(cond_export)
    situation_repas: str | None = None

    if rule.get("bonus_type_id"):
        resp = (
            supabase.table("company_bonus_types")
            .select(
                "libelle, soumise_a_cotisations, soumise_a_impot, export_code, "
                "situation_repas"
            )
            .eq("id", rule["bonus_type_id"])
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if rows:
            row = rows[0]
            libelle = str(row.get("libelle") or rule.get("label") or rule.get("code"))
            social = bool(row.get("soumise_a_cotisations", True))
            taxable = bool(row.get("soumise_a_impot", True))
            raw_export = row.get("export_code")
            export_code = str(raw_export) if raw_export else None
            raw_situation = row.get("situation_repas")
            situation_repas = str(raw_situation) if raw_situation else None
            if not catalog_id:
                low = libelle.lower()
                if "panier" in low or "repas" in low:
                    catalog_id = "indemnite_panier_repas"
            return libelle, social, taxable, catalog_id, export_code, situation_repas

    label = str(rule.get("label") or rule.get("code") or "Variable paie")
    if not catalog_id:
        low = label.lower()
        if "panier" in low or "repas" in low:
            catalog_id = "indemnite_panier_repas"
    return label, True, True, catalog_id, export_code, situation_repas


def _append_generated_input(
    *,
    preview: list[dict[str, Any]],
    written: int,
    dry_run: bool,
    rule: dict[str, Any],
    emp: dict[str, Any],
    eid: str,
    year: int,
    month: int,
    amount: float,
    quantity: float,
    name_suffix: str,
    details: dict[str, Any] | None = None,
) -> int:
    if amount <= 0:
        return written
    label, social, taxable, catalog_id, export_code, situation_repas = _bonus_type_meta(rule)
    input_name = f"{label} — {name_suffix}" if name_suffix else label
    entry: dict[str, Any] = {
        "employee_id": eid,
        "first_name": emp.get("first_name"),
        "last_name": emp.get("last_name"),
        "rule_code": rule.get("code"),
        "rule_label": rule.get("label"),
        "amount": amount,
        "quantity": quantity,
    }
    if details:
        entry["details"] = details
    preview.append(entry)
    if not dry_run and rule.get("generation_mode") == "auto":
        payload: dict[str, Any] = {
            "employee_id": eid,
            "year": year,
            "month": month,
            "name": input_name,
            "description": f"Auto: {rule.get('code')}",
            "amount": amount,
            "is_socially_taxed": social,
            "is_taxable": taxable,
            "payroll_quantity": quantity,
        }
        if rule.get("bonus_type_id"):
            payload["bonus_type_id"] = rule["bonus_type_id"]
        if catalog_id:
            payload["catalog_prime_id"] = catalog_id
        if export_code:
            payload["export_code"] = export_code
        if situation_repas:
            payload["situation_repas"] = situation_repas
        repo.upsert_monthly_input(payload)
        return written + 1
    return written


def generate_monthly_variables(
    company_id: str,
    year: int,
    month: int,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    rules = [r for r in repo.list_rules(company_id) if r.get("enabled")]
    emp_resp = (
        supabase.table("employees")
        .select(
            "id, first_name, last_name, statut, specificites_paie, "
            "salaire_de_base, duree_hebdomadaire, hire_date, contract_end_date"
        )
        .eq("company_id", company_id)
        .in_("employment_status", ["actif", "active"])
        .execute()
    )
    employees = emp_resp.data or []
    preview: list[dict[str, Any]] = []
    written = 0
    start, end = _month_bounds(year, month)
    employee_ids = [str(e["id"]) for e in employees]
    all_absences = list_validated_absences_for_employees_in_range(
        employee_ids, start, end
    )
    absences_by_employee: dict[str, list[dict[str, Any]]] = {}
    for row in all_absences:
        eid_key = str(row.get("employee_id") or "")
        if eid_key:
            absences_by_employee.setdefault(eid_key, []).append(row)
    special_days = repo.list_special_days(company_id, year, month)
    needs_km_bareme = any(
        r.get("rule_type") == "per_astreinte_weekend_km" for r in rules
    )
    baremes_km = _fetch_baremes_km() if needs_km_bareme else {}

    for rule in rules:
        conditions = rule.get("conditions") or {}
        rule_type = rule.get("rule_type") or ""
        for emp in employees:
            if not employee_matches_conditions(emp, conditions):
                continue
            eid = str(emp["id"])

            if rule_type == "transport_domicile_travail":
                # Le montant vient de la fiche salarié (avenant signé), pas de la
                # règle : une seule règle par entreprise sert tous les
                # bénéficiaires, chacun avec le sien.
                spec = emp.get("specificites_paie") or {}
                transport = (
                    (spec.get("transport") or {}) if isinstance(spec, dict) else {}
                )
                try:
                    contractuel = float(transport.get("indemnite_mensuelle_nette") or 0)
                except (TypeError, ValueError):
                    contractuel = 0.0
                if contractuel <= 0:
                    continue
                amount = montant_transport_mensuel(
                    contractuel,
                    debut_mois=start,
                    fin_mois=end,
                    date_entree=_parse_date_iso(emp.get("hire_date")),
                    date_sortie=_parse_date_iso(emp.get("contract_end_date")),
                    date_effet=_parse_date_iso(transport.get("indemnite_date_effet")),
                    absent_tout_le_mois=est_absent_tout_le_mois(
                        _jours_absence(absences_by_employee.get(eid, []), start, end),
                        start,
                        end,
                    ),
                )
                written = _append_generated_input(
                    preview=preview,
                    written=written,
                    dry_run=dry_run,
                    rule=rule,
                    emp=emp,
                    eid=eid,
                    year=year,
                    month=month,
                    amount=amount,
                    quantity=1.0,
                    name_suffix="",
                )
                continue

            if rule_type == "per_astreinte_weekend_km":
                manual_name = conditions.get("manual_trips_input_name")
                manual_trips = _load_manual_trips(
                    eid, year, month, str(manual_name) if manual_name else None
                )
                km_result = evaluate_astreinte_weekend_km(
                    rule,
                    emp,
                    year=year,
                    month=month,
                    calendrier_reel=_load_calendrier_reel(eid, year, month),
                    astreinte_shift_dates=_astreinte_shift_dates(eid, start, end),
                    baremes_km=baremes_km,
                    manual_trips=manual_trips,
                )
                amount = float(km_result.get("amount") or 0)
                qty = float(km_result.get("quantity") or 0)
                details = km_result.get("details") or {}
                show_skipped = dry_run and read_deplacement_astreinte(emp) is not None
                if amount <= 0 and not show_skipped:
                    continue
                label, social, taxable, catalog_id, export_code, situation_repas = _bonus_type_meta(rule)
                entry: dict[str, Any] = {
                    "employee_id": eid,
                    "first_name": emp.get("first_name"),
                    "last_name": emp.get("last_name"),
                    "rule_code": rule.get("code"),
                    "rule_label": rule.get("label"),
                    "amount": amount,
                    "quantity": qty,
                    "details": details,
                }
                preview.append(entry)
                if amount > 0 and not dry_run and rule.get("generation_mode") == "auto":
                    payload: dict[str, Any] = {
                        "employee_id": eid,
                        "year": year,
                        "month": month,
                        "name": label,
                        "description": f"Auto: {rule.get('code')}",
                        "amount": amount,
                        "is_socially_taxed": social,
                        "is_taxable": taxable,
                        "payroll_quantity": qty,
                    }
                    if rule.get("bonus_type_id"):
                        payload["bonus_type_id"] = rule["bonus_type_id"]
                    if catalog_id:
                        payload["catalog_prime_id"] = catalog_id
                    if export_code:
                        payload["export_code"] = export_code
                    if situation_repas:
                        payload["situation_repas"] = situation_repas
                    repo.upsert_monthly_input(payload)
                    written += 1
                continue

            if rule_type == "per_astreinte_week_tiered":
                payouts = evaluate_astreinte_week_tiered(
                    rule,
                    year=year,
                    month=month,
                    shift_dates=_astreinte_shift_dates(eid, start, end),
                    special_days=special_days,
                )
                for payout in payouts:
                    suffix = str(payout.get("monday") or payout.get("kind") or "")
                    written = _append_generated_input(
                        preview=preview,
                        written=written,
                        dry_run=dry_run,
                        rule=rule,
                        emp=emp,
                        eid=eid,
                        year=year,
                        month=month,
                        amount=float(payout.get("amount") or 0),
                        quantity=float(payout.get("quantity") or 1),
                        name_suffix=suffix,
                        details=payout.get("details"),
                    )
                continue

            if rule_type == "per_astreinte_weekend_majoration":
                hourly = resolve_hourly_rate(emp)
                majorations = evaluate_astreinte_weekend_majoration(
                    rule,
                    year=year,
                    month=month,
                    calendrier_reel=_load_calendrier_reel(eid, year, month),
                    astreinte_shift_dates=_astreinte_shift_dates(eid, start, end),
                    hourly_rate=hourly,
                )
                for maj in majorations:
                    suffix = str(maj.get("work_date") or "")
                    written = _append_generated_input(
                        preview=preview,
                        written=written,
                        dry_run=dry_run,
                        rule=rule,
                        emp=emp,
                        eid=eid,
                        year=year,
                        month=month,
                        amount=float(maj.get("amount") or 0),
                        quantity=float(maj.get("quantity") or 1),
                        name_suffix=suffix,
                        details=maj.get("details"),
                    )
                continue

            if rule_type == "per_week_without_absence":
                emp_absences = absences_by_employee.get(eid, [])
                shift_dates = list_locked_shift_dates_for_employee(
                    eid, start, end, company_id=company_id
                )
                presence = evaluate_presence_weeks(
                    year=year,
                    month=month,
                    absence_requests=emp_absences,
                    conditions=conditions,
                    locked_shift_dates=shift_dates,
                )
                qty = float(presence.get("quantity") or 0)
                amount = compute_rule_amount(
                    rule_type,
                    float(rule["amount"]) if rule.get("amount") is not None else None,
                    None,
                    qty,
                    conditions=conditions,
                )
                if qty <= 0 and not dry_run:
                    continue
                written = _append_generated_input(
                    preview=preview,
                    written=written,
                    dry_run=dry_run,
                    rule=rule,
                    emp=emp,
                    eid=eid,
                    year=year,
                    month=month,
                    amount=amount,
                    quantity=qty,
                    name_suffix="",
                    details=presence.get("details"),
                )
                continue

            qty = _resolve_quantity(rule, eid, company_id, year, month)
            amount = compute_rule_amount(
                rule_type,
                float(rule["amount"]) if rule.get("amount") is not None else None,
                float(rule["rate"]) if rule.get("rate") is not None else None,
                qty,
                conditions=conditions,
            )
            if amount <= 0:
                continue
            written = _append_generated_input(
                preview=preview,
                written=written,
                dry_run=dry_run,
                rule=rule,
                emp=emp,
                eid=eid,
                year=year,
                month=month,
                amount=amount,
                quantity=qty,
                name_suffix="",
            )

    return {
        "company_id": company_id,
        "year": year,
        "month": month,
        "dry_run": dry_run,
        "preview": preview,
        "written_count": written,
    }

# Export « Virement acomptes » — remise bancaire des acomptes et avances.
#
# Campagne de paiement distincte de celle des salaires : identifiants SEPA
# propres, date d'exécution propre, historique propre.
#
# Deux modes :
#   - « a_verser » (défaut) : les avances approuvées dont il reste un montant à
#     verser. Le fichier est un ORDRE donné à la banque. Aucun filtre de date par
#     défaut — un acompte approuvé fin juin et payé début juillet doit figurer
#     dans la remise de juillet.
#   - « verses » : les versements déjà enregistrés sur une fenêtre de dates.
#     C'est un relevé a posteriori.
#
# Cet export ne modifie aucun statut et ne crée aucun versement.
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import supabase
from app.modules.saisies_avances.domain.rules import advance_type_label
from app.shared.utils.export import format_period, generate_csv, generate_xlsx
from app.shared.utils.iban import (
    extract_bic,
    extract_iban,
    mask_iban,
    validate_iban,
)

MODE_A_VERSER = "a_verser"
MODE_VERSES = "verses"

# Colonnes du récapitulatif remis à l'utilisateur (sans les identifiants internes).
RECAP_HEADERS = [
    "Matricule",
    "Nom",
    "Prénom",
    "Nature",
    "IBAN",
    "BIC",
    "Montant",
    "Devise",
    "Date",
    "Libelle",
    "Statut_controle",
]

BANK_HEADERS = [
    "IBAN",
    "BIC",
    "Nom",
    "Prénom",
    "Montant",
    "Devise",
    "Libelle",
]


def _period_bounds(period: str) -> Tuple[str, str]:
    year, month = map(int, period.split("-"))
    last_day = monthrange(year, month)[1]
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


def _to_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _employee_name(employee: Dict[str, Any]) -> str:
    return f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip()


def _load_employees(employee_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    if not employee_ids:
        return {}
    r = (
        supabase.table("employees")
        .select(
            "id, first_name, last_name, coordonnees_bancaires, salary_payment_method"
        )
        .in_("id", [str(e) for e in employee_ids])
        .execute()
    )
    return {str(e["id"]): e for e in (r.data or []) if e.get("id")}


def _load_exits(company_id: str) -> Dict[str, Dict[str, Any]]:
    r = (
        supabase.table("employee_exits")
        .select("employee_id, exit_type, last_working_day, status")
        .eq("company_id", company_id)
        .execute()
    )
    return {str(e["employee_id"]): e for e in (r.data or []) if e.get("employee_id")}


def _total_paid_by_advance(advance_ids: List[str]) -> Dict[str, float]:
    """Somme des versements déjà enregistrés, par avance."""
    if not advance_ids:
        return {}
    r = (
        supabase.table("salary_advance_payments")
        .select("advance_id, payment_amount")
        .in_("advance_id", advance_ids)
        .execute()
    )
    totals: Dict[str, float] = {}
    for payment in r.data or []:
        key = str(payment.get("advance_id", "")).strip()
        if key:
            totals[key] = totals.get(key, 0.0) + _to_float(payment.get("payment_amount"))
    return totals


def _is_exited_before(exit_info: Dict[str, Any], reference: str) -> bool:
    last_working_day = exit_info.get("last_working_day")
    if not last_working_day:
        return False
    try:
        exit_date = (
            datetime.strptime(last_working_day, "%Y-%m-%d").date()
            if isinstance(last_working_day, str)
            else last_working_day
        )
        ref_date = datetime.strptime(reference[:10], "%Y-%m-%d").date()
        return exit_date < ref_date
    except (ValueError, TypeError):
        return False


def _payment_method(advance: Dict[str, Any], employee: Dict[str, Any]) -> str:
    """Mode de règlement : celui de l'acompte s'il est renseigné, sinon celui du salarié."""
    method = advance.get("payment_method") or employee.get("salary_payment_method")
    return (method or "virement").strip().lower()


def _fetch_advances_a_verser(
    company_id: str,
    period: str,
    limiter_au_mois: bool,
) -> List[Dict[str, Any]]:
    query = (
        supabase.table("salary_advances")
        .select("*")
        .eq("company_id", company_id)
        .eq("status", "approved")
    )
    if limiter_au_mois:
        period_start, period_end = _period_bounds(period)
        query = query.gte("requested_date", period_start).lte(
            "requested_date", period_end
        )
    return query.order("requested_date").execute().data or []


def _fetch_payments(
    company_id: str,
    period: str,
    date_debut: Optional[str],
    date_fin: Optional[str],
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Versements enregistrés sur la fenêtre, avec l'index des avances associées."""
    advances_r = (
        supabase.table("salary_advances")
        .select("*")
        .eq("company_id", company_id)
        .execute()
    )
    advances_map = {str(a["id"]): a for a in (advances_r.data or []) if a.get("id")}
    if not advances_map:
        return [], {}

    default_start, default_end = _period_bounds(period)
    start = date_debut or default_start
    end = date_fin or default_end

    payments_r = (
        supabase.table("salary_advance_payments")
        .select("*")
        .in_("advance_id", list(advances_map.keys()))
        .gte("payment_date", start)
        .lte("payment_date", end)
        .order("payment_date")
        .execute()
    )
    return payments_r.data or [], advances_map


def get_virement_acomptes_data(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    excluded_employee_ids: Optional[List[str]] = None,
    execution_date: Optional[str] = None,
    payment_label: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]], List[str]]:
    """Construit les lignes de virement, les totaux, les anomalies et les avertissements."""
    filters = filters or {}
    mode = filters.get("mode") or MODE_A_VERSER
    if mode not in (MODE_A_VERSER, MODE_VERSES):
        raise ValueError(
            f"Mode '{mode}' inconnu — attendu '{MODE_A_VERSER}' ou '{MODE_VERSES}'."
        )

    excluded_employees = {str(e) for e in (excluded_employee_ids or [])}
    kept_employees = {str(e) for e in (employee_ids or [])}
    excluded_advances = {str(a) for a in (filters.get("excluded_advance_ids") or [])}
    excluded_payments = {str(p) for p in (filters.get("excluded_payment_ids") or [])}

    period_label = format_period(period)
    default_label = payment_label or f"Acompte {period_label}"

    if mode == MODE_A_VERSER:
        source = _build_source_a_verser(
            company_id, period, bool(filters.get("limiter_au_mois"))
        )
    else:
        source = _build_source_verses(
            company_id,
            period,
            filters.get("date_debut"),
            filters.get("date_fin"),
        )

    employees_map = _load_employees([str(s["employee_id"]) for s in source])
    exits = _load_exits(company_id)
    reference_date = execution_date or date.today().isoformat()

    rows: List[Dict[str, Any]] = []
    anomalies: List[Dict[str, Any]] = []
    warnings: List[str] = []
    totals = {"virements_count": 0, "total_amount": 0.0, "currency": "EUR"}
    excluded_non_virement = 0

    for item in source:
        employee_id = str(item["employee_id"])
        advance_id = str(item["advance_id"])
        payment_id = str(item.get("payment_id") or "")

        if kept_employees and employee_id not in kept_employees:
            continue
        if employee_id in excluded_employees:
            continue
        if advance_id in excluded_advances:
            continue
        if payment_id and payment_id in excluded_payments:
            continue

        employee = employees_map.get(employee_id)
        if not employee:
            anomalies.append(
                {
                    "type": "error",
                    "message": f"Salarié introuvable pour l'acompte {advance_id[:8]}",
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": "",
                }
            )
            continue

        name = _employee_name(employee)

        if item.get("montant_indetermine"):
            anomalies.append(
                {
                    "type": "error",
                    "message": (
                        f"Acompte approuvé sans montant validé - {name}. "
                        "Renseignez le montant accordé avant de générer la remise."
                    ),
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": name,
                }
            )
            continue

        montant = round(_to_float(item["montant"]), 2)
        if montant <= 0:
            anomalies.append(
                {
                    "type": "error",
                    "message": f"Montant ≤ 0 - {name} ({item['nature']})",
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": name,
                }
            )
            continue

        if _payment_method(item["advance"], employee) in ("cheque", "especes"):
            excluded_non_virement += 1
            continue

        raw_coords = employee.get("coordonnees_bancaires")
        iban_clean = extract_iban(raw_coords)
        bic = extract_bic(raw_coords)

        if not validate_iban(iban_clean):
            anomalies.append(
                {
                    "type": "error",
                    "message": f"IBAN manquant ou invalide - {name}",
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": name,
                }
            )
            continue

        control_status = "OK"
        exit_info = exits.get(employee_id)
        if exit_info and _is_exited_before(exit_info, reference_date):
            control_status = "Alerte"
            motif = (
                "acompte à verser" if mode == MODE_A_VERSER else "acompte versé"
            )
            warnings.append(f"{name}: salarié sorti mais {motif}")

        rows.append(
            {
                "Matricule": employee_id[:8],
                "Nom": employee.get("last_name", ""),
                "Prénom": employee.get("first_name", ""),
                "Nature": item["nature"],
                "IBAN": iban_clean,
                "IBAN_Masque": mask_iban(iban_clean),
                "BIC": bic,
                "Montant": montant,
                "Devise": "EUR",
                "Date": item.get("date") or "",
                # Sans libellé imposé, chaque ligne porte sa nature : le salarié
                # lit « Acompte sur salaire » et non « Acompte » sur son relevé.
                "Libelle": default_label
                if payment_label
                else f"{item['nature']} {period_label}",
                "Statut_controle": control_status,
                "advance_id": advance_id,
                "payment_id": payment_id,
                "employee_id": employee_id,
            }
        )
        totals["virements_count"] += 1
        totals["total_amount"] = round(totals["total_amount"] + montant, 2)

    if excluded_non_virement:
        warnings.append(
            f"{excluded_non_virement} acompte(s) exclu(s) — règlement par chèque ou espèces."
        )

    totals["employees_count"] = len({r["employee_id"] for r in rows})
    return rows, totals, anomalies, warnings


def _build_source_a_verser(
    company_id: str,
    period: str,
    limiter_au_mois: bool,
) -> List[Dict[str, Any]]:
    """Avances approuvées dont il reste un montant à verser."""
    advances = _fetch_advances_a_verser(company_id, period, limiter_au_mois)
    if not advances:
        return []

    paid_map = _total_paid_by_advance([str(a["id"]) for a in advances])
    source: List[Dict[str, Any]] = []

    for advance in advances:
        advance_id = str(advance["id"])
        approved_raw = advance.get("approved_amount")
        nature = advance_type_label(
            advance.get("advance_type", "avance_salaire"), advance.get("prime_label")
        )

        # Une avance approuvée sans montant validé ne peut pas être virée : on la
        # remonte en anomalie bloquante plutôt que de la virer à 0 €.
        if approved_raw is None or approved_raw == "":
            source.append(
                {
                    "employee_id": advance.get("employee_id"),
                    "advance_id": advance_id,
                    "payment_id": None,
                    "advance": advance,
                    "nature": nature,
                    "montant": 0.0,
                    "montant_indetermine": True,
                    "date": advance.get("requested_date"),
                }
            )
            continue

        reste = round(_to_float(approved_raw) - paid_map.get(advance_id, 0.0), 2)
        if reste <= 0:
            continue

        source.append(
            {
                "employee_id": advance.get("employee_id"),
                "advance_id": advance_id,
                "payment_id": None,
                "advance": advance,
                "nature": nature,
                "montant": reste,
                "montant_indetermine": False,
                "date": advance.get("requested_date"),
            }
        )

    return source


def _build_source_verses(
    company_id: str,
    period: str,
    date_debut: Optional[str],
    date_fin: Optional[str],
) -> List[Dict[str, Any]]:
    """Versements d'acomptes déjà enregistrés sur la fenêtre demandée."""
    payments, advances_map = _fetch_payments(company_id, period, date_debut, date_fin)
    source: List[Dict[str, Any]] = []

    for payment in payments:
        advance = advances_map.get(str(payment.get("advance_id", "")))
        if not advance:
            continue
        source.append(
            {
                "employee_id": advance.get("employee_id"),
                "advance_id": str(advance["id"]),
                "payment_id": str(payment.get("id") or ""),
                "advance": advance,
                "nature": advance_type_label(
                    advance.get("advance_type", "avance_salaire"),
                    advance.get("prime_label"),
                ),
                "montant": _to_float(payment.get("payment_amount")),
                "montant_indetermine": False,
                "date": payment.get("payment_date"),
            }
        )

    return source


def _detect_paid_without_payment(company_id: str) -> List[str]:
    """Avances marquées « versée » sans aucun versement enregistré."""
    advances_r = (
        supabase.table("salary_advances")
        .select("id")
        .eq("company_id", company_id)
        .eq("status", "paid")
        .execute()
    )
    advance_ids = [str(a["id"]) for a in (advances_r.data or []) if a.get("id")]
    if not advance_ids:
        return []
    paid_map = _total_paid_by_advance(advance_ids)
    return [aid for aid in advance_ids if paid_map.get(aid, 0.0) <= 0]


def preview_virement_acomptes(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    excluded_employee_ids: Optional[List[str]] = None,
    execution_date: Optional[str] = None,
    payment_label: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    filters = filters or {}
    mode = filters.get("mode") or MODE_A_VERSER
    rows, totals, anomalies, warnings = get_virement_acomptes_data(
        company_id,
        period,
        employee_ids,
        excluded_employee_ids,
        execution_date,
        payment_label,
        filters,
    )

    if totals["virements_count"] == 0:
        warnings.append(
            "Aucun acompte à verser sur cette sélection."
            if mode == MODE_A_VERSER
            else "Aucun versement d'acompte enregistré sur cette fenêtre."
        )

    if mode == MODE_VERSES:
        if totals["virements_count"] > 0:
            # Le fichier bancaire produit dans ce mode reste un ordre de virement
            # valide : transmis à la banque, il paierait une seconde fois.
            warnings.append(
                "⚠ Ces acomptes ont DÉJÀ été versés : ce fichier est un relevé, "
                "pas un ordre de paiement. Ne le transmettez pas à la banque, "
                "elle exécuterait un second virement."
            )
        incoherentes = _detect_paid_without_payment(company_id)
        if incoherentes:
            warnings.append(
                f"{len(incoherentes)} acompte(s) marqué(s) « versé(e) » sans aucun "
                "versement enregistré — ils n'apparaissent pas dans ce fichier."
            )
    else:
        warnings.append(
            "Ce fichier n'enregistre aucun versement. Une fois la banque passée, "
            "enregistrez les versements depuis la fiche de l'acompte."
        )

    blocking = [a for a in anomalies if a.get("severity") == "blocking"]
    return {
        "employees_count": totals["employees_count"],
        "totals": {
            "employees_count": totals["employees_count"],
            "total_amount": totals["total_amount"],
        },
        "anomalies": anomalies,
        "warnings": warnings,
        "can_generate": len(blocking) == 0 and totals["virements_count"] > 0,
        "details": {"lines": [_recap_row(r) for r in rows]},
    }


def _recap_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {header: row.get(header, "") for header in RECAP_HEADERS}


def generate_virement_acomptes_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    excluded_employee_ids: Optional[List[str]] = None,
    execution_date: Optional[str] = None,
    payment_label: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    file_format: str = "csv",
) -> bytes:
    """Récapitulatif lisible de la remise."""
    rows, _, _, _ = get_virement_acomptes_data(
        company_id,
        period,
        employee_ids,
        excluded_employee_ids,
        execution_date,
        payment_label,
        filters,
    )
    recap = [_recap_row(r) for r in rows]
    if file_format == "xlsx":
        return generate_xlsx(
            recap, RECAP_HEADERS, f"Virement acomptes {format_period(period)}"
        )
    return generate_csv(recap, RECAP_HEADERS)


def generate_virement_acomptes_bank_file(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    excluded_employee_ids: Optional[List[str]] = None,
    execution_date: Optional[str] = None,
    payment_label: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Fichier bancaire au format CSV plat."""
    from app.modules.exports.infrastructure.export_sepa import filter_payable_rows

    rows, _, _, _ = get_virement_acomptes_data(
        company_id,
        period,
        employee_ids,
        excluded_employee_ids,
        execution_date,
        payment_label,
        filters,
    )
    bank_rows = [
        {header: row.get(header, "") for header in BANK_HEADERS}
        for row in filter_payable_rows(rows)
    ]
    return generate_csv(bank_rows, BANK_HEADERS)


def generate_virement_acomptes_sepa(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    excluded_employee_ids: Optional[List[str]] = None,
    execution_date: Optional[str] = None,
    payment_label: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    debtor_name: str = "Entreprise",
    debtor_iban: str = "",
    debtor_bic: str = "",
) -> bytes:
    """Remise SEPA pain.001.001.03 — campagne distincte de celle des salaires."""
    from app.modules.exports.infrastructure.export_sepa import build_pain001

    rows, _, _, _ = get_virement_acomptes_data(
        company_id,
        period,
        employee_ids,
        excluded_employee_ids,
        execution_date,
        payment_label,
        filters,
    )
    return build_pain001(
        rows,
        period=period,
        label=payment_label or f"Acompte {format_period(period)}",
        execution_date=execution_date,
        msg_prefix="EYWAI-ACO",
        payment_info_id=f"PMT-ACO-{period}",
        end_to_end_prefix="ACO",
        debtor_name=debtor_name,
        debtor_iban=debtor_iban,
        debtor_bic=debtor_bic,
    )

# Moteur d'écritures paie unifié — registre équilibré sans double comptabilisation.
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from typing import Any, Dict, List, Literal, Optional, Tuple

from app.modules.exports.domain.charges_organisme import resolve_organisme
from app.modules.exports.infrastructure.export_ecritures_comptables import (
    DEFAULT_MAPPINGS,
    get_accounting_mappings,
    get_default_mapping,
    get_payslip_data_for_od,
)
from app.shared.utils.export import format_period

Regroupement = Literal["global", "par_etablissement", "par_analytique"]
LedgerScope = Literal["full", "salaires", "charges_sociales", "pas", "auxiliaries"]

DEFAULT_LOAN_ACCOUNT = "274000"


def _round2(value: float) -> float:
    return round(value, 2)


def _resolve_mapping(
    mappings: Dict[str, Dict[str, Any]], rubrique_code: str
) -> Dict[str, Any]:
    return mappings.get(rubrique_code) or get_default_mapping(rubrique_code) or DEFAULT_MAPPINGS.get(rubrique_code, {})  # type: ignore[return-value]


def _period_end_date(period: str) -> str:
    year, month = map(int, period.split("-"))
    last_day = monthrange(year, month)[1]
    return f"{year}-{month:02d}-{last_day:02d}"


def _make_entry(
    *,
    date_ecriture: str,
    journal: str,
    compte: str,
    libelle: str,
    debit: float,
    credit: float,
    reference: str,
    period: str,
    analytique: Optional[str] = None,
    group_key: str = "global",
) -> Dict[str, Any]:
    return {
        "date_ecriture": date_ecriture,
        "journal": journal,
        "compte_comptable": compte,
        "libelle": libelle,
        "debit": _round2(debit),
        "credit": _round2(credit),
        "analytique": analytique,
        "reference_export": reference,
        "periode_paie": period,
        "group_key": group_key,
    }


def list_loan_repayments_by_period(
    company_id: str, period: str
) -> List[Dict[str, Any]]:
    from app.core.database import supabase

    year, month = map(int, period.split("-"))
    loans_r = (
        supabase.table("employee_loans")
        .select("id, employee_id")
        .eq("company_id", company_id)
        .execute()
    )
    loans = {str(r["id"]): r for r in (loans_r.data or []) if r.get("id")}
    if not loans:
        return []

    rep_r = (
        supabase.table("employee_loan_repayments")
        .select("*")
        .in_("loan_id", list(loans.keys()))
        .eq("year", year)
        .eq("month", month)
        .execute()
    )
    employee_ids = list(
        {str(loans[str(r["loan_id"])]["employee_id"]) for r in (rep_r.data or []) if r.get("loan_id") and str(r["loan_id"]) in loans}
    )
    employees_map: Dict[str, str] = {}
    if employee_ids:
        emp_r = (
            supabase.table("employees")
            .select("id, first_name, last_name")
            .in_("id", employee_ids)
            .execute()
        )
        for emp in emp_r.data or []:
            eid = str(emp.get("id", ""))
            name = f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()
            if eid and name:
                employees_map[eid] = name

    result: List[Dict[str, Any]] = []
    for rep in rep_r.data or []:
        loan_id = str(rep.get("loan_id", ""))
        loan = loans.get(loan_id)
        if not loan:
            continue
        capital = float(rep.get("capital_amount", 0) or 0)
        interest = float(rep.get("interest_amount", 0) or 0)
        total = capital + interest
        if total <= 0:
            continue
        eid = str(loan.get("employee_id", ""))
        result.append(
            {
                "employee_id": eid,
                "employee_name": employees_map.get(eid, ""),
                "capital_amount": capital,
                "interest_amount": interest,
                "total_amount": total,
                "loan_id": loan_id,
            }
        )
    return result


def _append_core_salary_entries(
    ecritures: List[Dict[str, Any]],
    sub_totals: Dict[str, float],
    *,
    date_ecriture: str,
    period: str,
    period_label: str,
    reference: str,
    group_key: str,
    mappings: Dict[str, Dict[str, Any]],
    label_suffix: str = "",
) -> None:
    suffix = f" — {label_suffix}" if label_suffix and label_suffix != "global" else ""
    m_brut = _resolve_mapping(mappings, "salaire_brut")
    m_net = _resolve_mapping(mappings, "net_a_payer")
    m_cot_sal = _resolve_mapping(mappings, "cotisation_salariale")
    m_pas = _resolve_mapping(mappings, "pas")

    if sub_totals.get("total_brut", 0) > 0 and m_brut:
        ecritures.append(
            _make_entry(
                date_ecriture=date_ecriture,
                journal=m_brut.get("journal", "OD"),
                compte=m_brut["compte_comptable"],
                libelle=f"Salaires {period_label}{suffix}",
                debit=sub_totals["total_brut"],
                credit=0.0,
                reference=reference,
                period=period,
                analytique=m_brut.get("analytique"),
                group_key=group_key,
            )
        )
    if sub_totals.get("total_net_a_payer", 0) > 0 and m_net:
        ecritures.append(
            _make_entry(
                date_ecriture=date_ecriture,
                journal=m_net.get("journal", "OD"),
                compte=m_net["compte_comptable"],
                libelle=f"Net à payer {period_label}{suffix}",
                debit=0.0,
                credit=sub_totals["total_net_a_payer"],
                reference=reference,
                period=period,
                analytique=m_net.get("analytique"),
                group_key=group_key,
            )
        )
    if sub_totals.get("total_cotisations_salariales", 0) > 0 and m_cot_sal:
        ecritures.append(
            _make_entry(
                date_ecriture=date_ecriture,
                journal=m_cot_sal.get("journal", "OD"),
                compte=m_cot_sal["compte_comptable"],
                libelle=f"Cotisations salariales {period_label}{suffix}",
                debit=0.0,
                credit=sub_totals["total_cotisations_salariales"],
                reference=reference,
                period=period,
                analytique=m_cot_sal.get("analytique"),
                group_key=group_key,
            )
        )
    if sub_totals.get("total_pas", 0) > 0 and m_pas:
        ecritures.append(
            _make_entry(
                date_ecriture=date_ecriture,
                journal=m_pas.get("journal", "OD"),
                compte=m_pas["compte_comptable"],
                libelle=f"PAS {period_label}{suffix}",
                debit=0.0,
                credit=sub_totals["total_pas"],
                reference=reference,
                period=period,
                analytique=m_pas.get("analytique"),
                group_key=group_key,
            )
        )


def build_payroll_ledger(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    date_ecriture: Optional[str] = None,
    regroupement: Regroupement = "global",
    include_notes_frais: bool = False,
    scope: LedgerScope = "full",
) -> Tuple[List[Dict[str, Any]], Dict[str, float], Dict[str, Any]]:
    if scope == "full":
        include_notes_frais = True
    """
    Construit le registre d'écritures paie équilibré pour une période.

    Structure PCG :
    - Débit 641 (brut)
    - Crédit 425 (net), 43x (cot. sal.), 442 (PAS), 427 (saisies), 425x (acomptes), 274 (prêts)
    - Débit 645 (charges patronales par organisme)
    - Crédit 431 (dettes organismes)
    """
    from app.modules.exports.infrastructure.export_acomptes import (
        get_acomptes_data,
    )
    from app.modules.exports.infrastructure.export_saisies import (
        get_saisies_data,
    )

    payslip_list, totals = get_payslip_data_for_od(
        company_id, period, employee_ids, "od_globale"
    )
    mappings = get_accounting_mappings(company_id)
    if not date_ecriture:
        date_ecriture = _period_end_date(period)

    period_label = format_period(period)
    reference = f"OD_PAIE_{period}"
    ecritures: List[Dict[str, Any]] = []

    m_brut = _resolve_mapping(mappings, "salaire_brut")
    m_net = _resolve_mapping(mappings, "net_a_payer")
    m_cot_sal = _resolve_mapping(mappings, "cotisation_salariale")
    m_cot_pat = _resolve_mapping(mappings, "cotisation_patronale")
    m_dette = _resolve_mapping(mappings, "dette_organisme")

    group_key = "global"
    if regroupement == "par_analytique" and m_brut.get("analytique"):
        group_key = str(m_brut.get("analytique"))

    if regroupement == "par_etablissement":
        subtotals_by_est: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {
                "total_brut": 0.0,
                "total_net_a_payer": 0.0,
                "total_cotisations_salariales": 0.0,
                "total_pas": 0.0,
            }
        )
        for payslip in payslip_list:
            est = payslip.get("establishment_label") or "Principal"
            subtotals_by_est[est]["total_brut"] += payslip.get("brut", 0)
            subtotals_by_est[est]["total_net_a_payer"] += payslip.get("net_a_payer", 0)
            subtotals_by_est[est]["total_cotisations_salariales"] += payslip.get(
                "cotisations_salariales", 0
            )
            subtotals_by_est[est]["total_pas"] += payslip.get("pas", 0)
        for est, sub in subtotals_by_est.items():
            _append_core_salary_entries(
                ecritures,
                sub,
                date_ecriture=date_ecriture,
                period=period,
                period_label=period_label,
                reference=reference,
                group_key=est,
                mappings=mappings,
                label_suffix=est,
            )
    else:
        _append_core_salary_entries(
            ecritures,
            totals,
            date_ecriture=date_ecriture,
            period=period,
            period_label=period_label,
            reference=reference,
            group_key=group_key,
            mappings=mappings,
        )

    charges_par_caisse: Dict[str, float] = defaultdict(float)
    dettes_par_groupe: Dict[str, float] = defaultdict(float)
    for payslip in payslip_list:
        entry_group = (
            payslip.get("establishment_label") or "Principal"
            if regroupement == "par_etablissement"
            else group_key
        )
        for coti in payslip.get("cotisations_detail", []):
            if not isinstance(coti, dict):
                continue
            libelle_cot = coti.get("libelle", "Cotisation")
            organisme = resolve_organisme(libelle_cot)
            montant_pat = float(coti.get("montant_patronal", 0) or 0)
            if montant_pat > 0 and m_cot_pat:
                key = f"{entry_group}::{organisme}::{libelle_cot}"
                charges_par_caisse[key] += montant_pat
                dettes_par_groupe[entry_group] += montant_pat
                ecritures.append(
                    _make_entry(
                        date_ecriture=date_ecriture,
                        journal=m_cot_pat.get("journal", "OD"),
                        compte=m_cot_pat["compte_comptable"],
                        libelle=f"Charges {libelle_cot} — {organisme} {period_label}",
                        debit=montant_pat,
                        credit=0.0,
                        reference=reference,
                        period=period,
                        analytique=m_cot_pat.get("analytique"),
                        group_key=entry_group,
                    )
                )

    if regroupement == "par_etablissement":
        for est, total_charges in dettes_par_groupe.items():
            if total_charges > 0 and m_dette:
                ecritures.append(
                    _make_entry(
                        date_ecriture=date_ecriture,
                        journal=m_dette.get("journal", "OD"),
                        compte=m_dette["compte_comptable"],
                        libelle=f"Dettes organismes sociaux {period_label} — {est}",
                        debit=0.0,
                        credit=total_charges,
                        reference=reference,
                        period=period,
                        analytique=m_dette.get("analytique"),
                        group_key=est,
                    )
                )
    else:
        total_charges = sum(
            float(coti.get("montant_patronal", 0) or 0)
            for payslip in payslip_list
            for coti in payslip.get("cotisations_detail", [])
            if isinstance(coti, dict)
        )
        if total_charges > 0 and m_dette:
            ecritures.append(
                _make_entry(
                    date_ecriture=date_ecriture,
                    journal=m_dette.get("journal", "OD"),
                    compte=m_dette["compte_comptable"],
                    libelle=f"Dettes organismes sociaux {period_label}",
                    debit=0.0,
                    credit=total_charges,
                    reference=reference,
                    period=period,
                    analytique=m_dette.get("analytique"),
                    group_key=group_key,
                )
            )

    _, repayments, _, _ = get_acomptes_data(company_id, period)
    for rep in repayments:
        montant = float(rep.get("amount_repaid", 0) or 0)
        if montant <= 0:
            continue
        compte = str(rep.get("accounting_account") or "425100")
        employee = rep.get("employee_name", "")
        nature = rep.get("advance_type_label", "Acompte")
        libelle = f"Remboursement {nature} — {employee} — {period_label}"
        ecritures.append(
            _make_entry(
                date_ecriture=date_ecriture,
                journal="OD",
                compte=compte,
                libelle=libelle,
                debit=0.0,
                credit=montant,
                reference=f"ACOMPTE_R_{period}",
                period=period,
                group_key=group_key,
            )
        )

    deductions, _, _ = get_saisies_data(company_id, period)
    m_saisie = _resolve_mapping(mappings, "saisie_opposition")
    for ded in deductions:
        montant = float(ded.get("deducted_amount", 0) or 0)
        if montant <= 0:
            continue
        compte = str(ded.get("accounting_account") or m_saisie.get("compte_comptable", "427000"))
        employee = ded.get("employee_name", "")
        nature = ded.get("seizure_type_label", "Saisie")
        creditor = ded.get("creditor_name", "")
        libelle = " — ".join(p for p in [nature, employee, creditor] if p) + f" — {period_label}"
        ecritures.append(
            _make_entry(
                date_ecriture=date_ecriture,
                journal=m_saisie.get("journal", "OD"),
                compte=compte,
                libelle=libelle,
                debit=0.0,
                credit=montant,
                reference=f"SAISIE_{period}",
                period=period,
                group_key=group_key,
            )
        )

    m_loan = _resolve_mapping(mappings, "pret_employeur")
    loan_repayments = list_loan_repayments_by_period(company_id, period)
    for rep in loan_repayments:
        montant = float(rep.get("total_amount", 0) or 0)
        if montant <= 0:
            continue
        employee = rep.get("employee_name", "")
        libelle = f"Remboursement prêt employeur — {employee} — {period_label}"
        compte = m_loan.get("compte_comptable", DEFAULT_LOAN_ACCOUNT)
        ecritures.append(
            _make_entry(
                date_ecriture=date_ecriture,
                journal=m_loan.get("journal", "OD"),
                compte=compte,
                libelle=libelle,
                debit=0.0,
                credit=montant,
                reference=f"PRET_{period}",
                period=period,
                group_key=group_key,
            )
        )

    if include_notes_frais:
        from app.modules.exports.infrastructure.export_notes_frais import (
            get_notes_frais_ecritures,
        )

        nf_ecritures = get_notes_frais_ecritures(
            company_id, period, employee_ids, date_ecriture
        )
        ecritures.extend(nf_ecritures)

    if regroupement == "global":
        final_ecritures = ecritures
    else:
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for e in ecritures:
            grouped[e.get("group_key", "global")].append(e)
        final_ecritures = []
        for group_entries in grouped.values():
            final_ecritures.extend(group_entries)

    if scope != "full":
        final_ecritures = _filter_by_scope(final_ecritures, scope)

    total_debit = sum(e["debit"] for e in final_ecritures)
    total_credit = sum(e["credit"] for e in final_ecritures)
    od_totals = {
        "total_debit": _round2(total_debit),
        "total_credit": _round2(total_credit),
        "equilibre": abs(total_debit - total_credit) < 0.01,
        "ecart": _round2(abs(total_debit - total_credit)),
    }
    return final_ecritures, od_totals, mappings


def _filter_by_scope(
    ecritures: List[Dict[str, Any]], scope: LedgerScope
) -> List[Dict[str, Any]]:
    """Filtre les écritures selon le type d'OD demandé."""
    if scope == "full":
        return ecritures

    ref = ecritures[0].get("reference_export", "") if ecritures else ""
    period_ref = ref.split("_")[-1] if ref else ""

    def _is_salaires(e: Dict[str, Any]) -> bool:
        lib = e.get("libelle", "")
        ref_e = e.get("reference_export", "")
        return ref_e.startswith("OD_PAIE_") and (
            lib.startswith("Salaires")
            or lib.startswith("Net à payer")
            or lib.startswith("Cotisations salariales")
        )

    def _is_charges(e: Dict[str, Any]) -> bool:
        lib = e.get("libelle", "")
        return lib.startswith("Charges ") or lib.startswith("Dettes organismes")

    def _is_pas(e: Dict[str, Any]) -> bool:
        return e.get("libelle", "").startswith("PAS ")

    def _is_auxiliary(e: Dict[str, Any]) -> bool:
        ref_e = e.get("reference_export", "")
        return ref_e.startswith(("ACOMPTE_", "SAISIE_", "PRET_", "NDF-"))

    filters = {
        "salaires": _is_salaires,
        "charges_sociales": _is_charges,
        "pas": _is_pas,
        "auxiliaries": _is_auxiliary,
    }
    predicate = filters.get(scope)
    if not predicate:
        return ecritures
    return [e for e in ecritures if predicate(e)]


def ledger_to_od_export_rows(ecritures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convertit les écritures registre vers le format export OD standard."""
    return [
        {
            "date_ecriture": e["date_ecriture"],
            "journal": e["journal"],
            "compte_comptable": e["compte_comptable"],
            "libelle": e["libelle"],
            "debit": e["debit"],
            "credit": e["credit"],
            "analytique": e.get("analytique"),
            "reference_export": e.get("reference_export", ""),
            "periode_paie": e["periode_paie"],
        }
        for e in ecritures
    ]

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


class _BalanceTracker:
    """Trace débit/crédit par composante pour diagnostiquer un OD déséquilibrée."""

    def __init__(self) -> None:
        self.debit: Dict[str, float] = defaultdict(float)
        self.credit: Dict[str, float] = defaultdict(float)
        self.skipped: List[str] = []

    def add_debit(self, component: str, amount: float) -> None:
        if amount > 0:
            self.debit[component] += amount

    def add_credit(self, component: str, amount: float) -> None:
        if amount > 0:
            self.credit[component] += amount

    def skip(self, message: str) -> None:
        self.skipped.append(message)

    def finalize(
        self,
        *,
        payslips_count: int,
        ecritures_lines: int,
        payslip_source_totals: Dict[str, Any],
        period: str,
        payslip_list: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        total_debit = _round2(sum(self.debit.values()))
        total_credit = _round2(sum(self.credit.values()))
        ecart = _round2(abs(total_debit - total_credit))
        if total_debit > total_credit + 0.005:
            heavier_side = "debit"
            interpretation = (
                f"Excédent de débit de {ecart}€ : il manque {ecart}€ de crédits "
                f"pour équilibrer l'OD."
            )
        elif total_credit > total_debit + 0.005:
            heavier_side = "credit"
            interpretation = (
                f"Excédent de crédit de {ecart}€ : il manque {ecart}€ de débits "
                f"pour équilibrer l'OD."
            )
        else:
            heavier_side = "balanced"
            interpretation = "OD équilibrée."

        charges_pat_debit = _round2(self.debit.get("charges_patronales", 0))
        charges_pat_allegements = _round2(
            self.credit.get("charges_patronales_allegements", 0)
        )
        charges_pat_net = _round2(charges_pat_debit - charges_pat_allegements)
        dettes_credit = _round2(self.credit.get("dettes_organismes", 0))
        bulletin_charges_pat = _round2(
            float(payslip_source_totals.get("total_cotisations_patronales", 0) or 0)
        )
        gap_analysis = _build_gap_analysis(
            payslip_source_totals=payslip_source_totals,
            debit_by_component=dict(self.debit),
            credit_by_component=dict(self.credit),
            ecart=ecart,
            payslip_list=payslip_list,
        )

        return {
            "period": period,
            "formula": "ecart = |total_debit - total_credit|",
            "total_debit": total_debit,
            "total_credit": total_credit,
            "ecart": ecart,
            "heavier_side": heavier_side,
            "interpretation": interpretation,
            "payslips_included": payslips_count,
            "ecritures_lines": ecritures_lines,
            "debit_by_component": {
                k: _round2(v) for k, v in sorted(self.debit.items()) if v > 0
            },
            "credit_by_component": {
                k: _round2(v) for k, v in sorted(self.credit.items()) if v > 0
            },
            "payslip_source_totals": {
                k: _round2(float(v)) if isinstance(v, (int, float)) else v
                for k, v in payslip_source_totals.items()
            },
            "reconciliation": {
                "charges_patronales_debitees_645": charges_pat_debit,
                "allegements_credites_645": charges_pat_allegements,
                "charges_patronales_nettes_645": charges_pat_net,
                "dettes_organismes_creditees_431": dettes_credit,
                "charges_patronales_dans_bulletins": bulletin_charges_pat,
                "ecart_645_net_vs_431": _round2(abs(charges_pat_net - dettes_credit)),
                "ecart_bulletins_vs_645_net": _round2(
                    abs(bulletin_charges_pat - charges_pat_net)
                ),
            },
            "skipped_entries": self.skipped,
            "gap_analysis": gap_analysis,
        }


def _build_gap_analysis(
    *,
    payslip_source_totals: Dict[str, Any],
    debit_by_component: Dict[str, float],
    credit_by_component: Dict[str, float],
    ecart: float,
    payslip_list: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    brut = float(payslip_source_totals.get("total_brut", 0) or 0)
    net = float(payslip_source_totals.get("total_net_a_payer", 0) or 0)
    cot_sal_src = float(payslip_source_totals.get("total_cotisations_salariales", 0) or 0)
    pas_src = float(payslip_source_totals.get("total_pas", 0) or 0)
    cot_pat_src = float(payslip_source_totals.get("total_cotisations_patronales", 0) or 0)

    prets = float(credit_by_component.get("prets_employeur", 0) or 0)
    saisies = float(credit_by_component.get("saisies", 0) or 0)
    allegements_645 = float(
        credit_by_component.get("charges_patronales_allegements", 0) or 0
    )

    credited_net = float(credit_by_component.get("net_a_payer", 0) or 0)
    credited_cot_sal = float(credit_by_component.get("cotisations_salariales", 0) or 0)
    credited_pas = float(credit_by_component.get("pas", 0) or 0)

    aux_credits = _round2(prets + saisies)
    expected_salary_credits = _round2(net + cot_sal_src + pas_src + aux_credits)
    salary_residual = _round2(brut - expected_salary_credits)

    missing_in_od = {
        "cotisations_salariales": _round2(max(0.0, cot_sal_src - credited_cot_sal)),
        "pas": _round2(max(0.0, pas_src - credited_pas)),
        "net_a_payer": _round2(max(0.0, net - credited_net)),
    }
    charges_pat_brut_od = float(debit_by_component.get("charges_patronales", 0) or 0)
    charges_pat_net_od = _round2(charges_pat_brut_od - allegements_645)
    missing_charges_pat = _round2(max(0.0, cot_pat_src - charges_pat_net_od))
    missing_dettes_org = _round2(
        max(
            0.0,
            cot_pat_src - float(credit_by_component.get("dettes_organismes", 0) or 0),
        )
    )

    likely_causes: List[Dict[str, Any]] = []
    if brut > 0 and cot_sal_src == 0 and pas_src == 0:
        likely_causes.append(
            {
                "code": "bulletins_sans_cotisations_extraites",
                "label": "Cotisations et PAS lus à 0 dans les bulletins (format ou extraction)",
                "montant_estime": ecart,
            }
        )
    for key, label in (
        ("cotisations_salariales", "Cotisations salariales non créditées en OD"),
        ("pas", "PAS non crédité en OD"),
        ("net_a_payer", "Net à payer non crédité en OD"),
    ):
        amount = missing_in_od[key]
        if amount > 0.01:
            likely_causes.append(
                {"code": f"missing_{key}", "label": label, "montant": amount}
            )
    dettes_org = float(credit_by_component.get("dettes_organismes", 0) or 0)
    ecart_645_431 = _round2(abs(charges_pat_net_od - dettes_org))
    if ecart_645_431 > 0.01:
        likely_causes.append(
            {
                "code": "ecart_charges_645_vs_dettes_431",
                "label": "Écart charges patronales nettes (645) vs dettes organismes (431)",
                "montant": ecart_645_431,
            }
        )
    if allegements_645 > 0.01 and ecart_645_431 > 0.01:
        likely_causes.append(
            {
                "code": "allegements_patronaux",
                "label": f"Allègements patronaux crédités en 645 ({allegements_645}€) — vérifier le rapprochement",
                "montant": allegements_645,
            }
        )
    if missing_charges_pat > 0.01:
        likely_causes.append(
            {
                "code": "missing_charges_patronales",
                "label": "Charges patronales nettes (645) inférieures aux bulletins",
                "montant": missing_charges_pat,
            }
        )
    if missing_dettes_org > 0.01:
        likely_causes.append(
            {
                "code": "missing_dettes_organismes",
                "label": "Dettes organismes (431) non créditées",
                "montant": missing_dettes_org,
            }
        )

    payslips_breakdown: List[Dict[str, Any]] = []
    bulletins_sans_lignes = 0
    for payslip in payslip_list or []:
        detail_count = len(payslip.get("cotisations_detail") or [])
        cot_sal = float(payslip.get("cotisations_salariales", 0) or 0)
        pas = float(payslip.get("pas", 0) or 0)
        if cot_sal == 0 and pas == 0 and float(payslip.get("brut", 0) or 0) > 0:
            bulletins_sans_lignes += 1
        payslips_breakdown.append(
            {
                "employee_name": payslip.get("employee_name", ""),
                "brut": _round2(float(payslip.get("brut", 0) or 0)),
                "net_a_payer": _round2(float(payslip.get("net_a_payer", 0) or 0)),
                "cotisations_salariales": _round2(cot_sal),
                "cotisations_patronales": _round2(
                    float(payslip.get("cotisations_patronales", 0) or 0)
                ),
                "pas": _round2(pas),
                "lignes_cotisations": detail_count,
            }
        )

    return {
        "salary_equation": {
            "formula": "brut ≈ net + cotisations_salariales + PAS + prêts + saisies",
            "brut_bulletins": _round2(brut),
            "net_bulletins": _round2(net),
            "cotisations_salariales_bulletins": _round2(cot_sal_src),
            "pas_bulletins": _round2(pas_src),
            "prets_employeur_od": _round2(prets),
            "saisies_od": _round2(saisies),
            "note_acomptes": "Les remboursements d'acomptes sont un mouvement interne 425 (débit/crédit) sans impact sur l'équilibre OD",
            "credits_attendus_cote_salaire": expected_salary_credits,
            "residu_equation": salary_residual,
            "residu_proche_ecart_od": abs(salary_residual - ecart) < 0.02,
        },
        "missing_in_od_vs_bulletins": missing_in_od,
        "charges_patronales_manquantes_od": missing_charges_pat,
        "dettes_organismes_manquantes_od": missing_dettes_org,
        "likely_causes": likely_causes,
        "bulletins_sans_cotisations_extraites": bulletins_sans_lignes,
        "payslips_breakdown": payslips_breakdown,
    }


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
    tracker: Optional[_BalanceTracker] = None,
) -> None:
    suffix = f" — {label_suffix}" if label_suffix and label_suffix != "global" else ""
    m_brut = _resolve_mapping(mappings, "salaire_brut")
    m_net = _resolve_mapping(mappings, "net_a_payer")
    m_cot_sal = _resolve_mapping(mappings, "cotisation_salariale")
    m_pas = _resolve_mapping(mappings, "pas")

    brut = float(sub_totals.get("total_brut", 0) or 0)
    if brut > 0 and m_brut:
        ecritures.append(
            _make_entry(
                date_ecriture=date_ecriture,
                journal=m_brut.get("journal", "OD"),
                compte=m_brut["compte_comptable"],
                libelle=f"Salaires {period_label}{suffix}",
                debit=brut,
                credit=0.0,
                reference=reference,
                period=period,
                analytique=m_brut.get("analytique"),
                group_key=group_key,
            )
        )
        if tracker:
            tracker.add_debit("salaire_brut", brut)
    elif brut > 0 and tracker:
        tracker.skip(f"salaire_brut non posté ({_round2(brut)}€) : mapping manquant")

    net = float(sub_totals.get("total_net_a_payer", 0) or 0)
    if net > 0 and m_net:
        ecritures.append(
            _make_entry(
                date_ecriture=date_ecriture,
                journal=m_net.get("journal", "OD"),
                compte=m_net["compte_comptable"],
                libelle=f"Net à payer {period_label}{suffix}",
                debit=0.0,
                credit=net,
                reference=reference,
                period=period,
                analytique=m_net.get("analytique"),
                group_key=group_key,
            )
        )
        if tracker:
            tracker.add_credit("net_a_payer", net)
    elif net > 0 and tracker:
        tracker.skip(f"net_a_payer non posté ({_round2(net)}€) : mapping manquant")

    cot_sal = float(sub_totals.get("total_cotisations_salariales", 0) or 0)
    if cot_sal > 0 and m_cot_sal:
        ecritures.append(
            _make_entry(
                date_ecriture=date_ecriture,
                journal=m_cot_sal.get("journal", "OD"),
                compte=m_cot_sal["compte_comptable"],
                libelle=f"Cotisations salariales {period_label}{suffix}",
                debit=0.0,
                credit=cot_sal,
                reference=reference,
                period=period,
                analytique=m_cot_sal.get("analytique"),
                group_key=group_key,
            )
        )
        if tracker:
            tracker.add_credit("cotisations_salariales", cot_sal)
    elif cot_sal > 0 and tracker:
        tracker.skip(
            f"cotisations_salariales non postées ({_round2(cot_sal)}€) : mapping manquant"
        )

    pas = float(sub_totals.get("total_pas", 0) or 0)
    if pas > 0 and m_pas:
        ecritures.append(
            _make_entry(
                date_ecriture=date_ecriture,
                journal=m_pas.get("journal", "OD"),
                compte=m_pas["compte_comptable"],
                libelle=f"PAS {period_label}{suffix}",
                debit=0.0,
                credit=pas,
                reference=reference,
                period=period,
                analytique=m_pas.get("analytique"),
                group_key=group_key,
            )
        )
        if tracker:
            tracker.add_credit("pas", pas)
    elif pas > 0 and tracker:
        tracker.skip(f"pas non posté ({_round2(pas)}€) : mapping manquant")


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
    tracker = _BalanceTracker()

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
                tracker=tracker,
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
            tracker=tracker,
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
            if montant_pat == 0:
                continue
            if not m_cot_pat:
                tracker.skip(
                    f"charge patronale non postée ({_round2(abs(montant_pat))}€, {libelle_cot}) : mapping manquant"
                )
                continue
            dettes_par_groupe[entry_group] += montant_pat
            if montant_pat > 0:
                key = f"{entry_group}::{organisme}::{libelle_cot}"
                charges_par_caisse[key] += montant_pat
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
                tracker.add_debit("charges_patronales", montant_pat)
            else:
                allegement = abs(montant_pat)
                ecritures.append(
                    _make_entry(
                        date_ecriture=date_ecriture,
                        journal=m_cot_pat.get("journal", "OD"),
                        compte=m_cot_pat["compte_comptable"],
                        libelle=f"Allègement {libelle_cot} — {organisme} {period_label}",
                        debit=0.0,
                        credit=allegement,
                        reference=reference,
                        period=period,
                        analytique=m_cot_pat.get("analytique"),
                        group_key=entry_group,
                    )
                )
                tracker.add_credit("charges_patronales_allegements", allegement)

    if regroupement == "par_etablissement":
        for est, total_charges in dettes_par_groupe.items():
            if abs(total_charges) > 0.005 and m_dette:
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
                tracker.add_credit("dettes_organismes", total_charges)
            elif abs(total_charges) > 0.005:
                tracker.skip(
                    f"dettes organismes non créditées ({_round2(total_charges)}€, {est}) : mapping manquant"
                )
    else:
        total_charges = _round2(
            sum(
                float(payslip.get("cotisations_patronales", 0) or 0)
                for payslip in payslip_list
            )
        )
        if abs(total_charges) > 0.005 and m_dette:
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
            tracker.add_credit("dettes_organismes", total_charges)
        elif abs(total_charges) > 0.005:
            tracker.skip(
                f"dettes organismes non créditées ({_round2(total_charges)}€) : mapping manquant"
            )

    m_net_acompte = _resolve_mapping(mappings, "net_a_payer")
    net_account = str(m_net_acompte.get("compte_comptable") or "425000")

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
                compte=net_account,
                libelle=libelle,
                debit=montant,
                credit=0.0,
                reference=f"ACOMPTE_R_{period}",
                period=period,
                group_key=group_key,
            )
        )
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
        tracker.add_debit("acomptes_remboursement_425", montant)
        tracker.add_credit("acomptes", montant)

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
        tracker.add_credit("saisies", montant)

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
        tracker.add_credit("prets_employeur", montant)

    if include_notes_frais:
        from app.modules.exports.infrastructure.export_notes_frais import (
            get_notes_frais_ecritures,
        )

        nf_ecritures = get_notes_frais_ecritures(
            company_id, period, employee_ids, date_ecriture
        )
        for nf in nf_ecritures:
            tracker.add_debit("notes_frais", float(nf.get("debit", 0) or 0))
            tracker.add_credit("notes_frais", float(nf.get("credit", 0) or 0))
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
    balance_debug = tracker.finalize(
        payslips_count=len(payslip_list),
        ecritures_lines=len(final_ecritures),
        payslip_source_totals=totals,
        period=period,
        payslip_list=payslip_list,
    )
    od_totals = {
        "total_debit": _round2(total_debit),
        "total_credit": _round2(total_credit),
        "equilibre": abs(total_debit - total_credit) < 0.01,
        "ecart": _round2(abs(total_debit - total_credit)),
        "balance_debug": balance_debug,
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

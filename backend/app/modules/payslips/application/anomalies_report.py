"""
Rapport d'anomalies sur les bulletins d'un mois (contrôles métier paie).

Indépendant des exports journal / DSN : règles dédiées GET /api/payslips/anomalies.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.database import supabase

from app.modules.payroll.infrastructure.analytics_repository import (
    payroll_analytics_repository,
)
from app.modules.payslips.domain.anomaly_visibility import (
    EmployeeAnomalyContext,
    is_system_config_anomaly,
    parse_date_value,
    should_include_anomaly_in_report,
    should_include_payslip_in_anomalies_report,
)
from app.modules.payslips.domain.comparison_engine import _sum_travail_base_hours, _to_float
from app.modules.payroll.engine.controles_convention import (
    NET_SUPERIEUR_BRUT_MESSAGE,
    extraire_alertes_rh_depuis_bulletin,
)
from app.modules.payslips.schemas.anomalies import (
    AnomaliePayslipItem,
    PayslipsAnomaliesReport,
)

SMIC_HORAIRE_2024 = 11.65
TAUX_HORAIRE_MIN = SMIC_HORAIRE_2024 * 0.8
TAUX_HORAIRE_MAX = 500.0


def _employee_name(emp: Any) -> str:
    if isinstance(emp, list) and emp:
        emp = emp[0]
    if not isinstance(emp, dict):
        return ""
    fn = str(emp.get("first_name") or "").strip()
    ln = str(emp.get("last_name") or "").strip()
    return f"{fn} {ln}".strip() or "—"


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None
    return None


def _sum_primes_from_brut(calcul_du_brut: Any) -> float:
    total = 0.0
    if not isinstance(calcul_du_brut, list):
        return total
    for line in calcul_du_brut:
        if not isinstance(line, dict):
            continue
        lib = str(line.get("libelle") or "").lower()
        if "prime" not in lib:
            continue
        total += float(line.get("gain") or 0) or 0.0
    return round(total, 2)


def _sum_cotisations_patronales(payslip_data: Dict[str, Any]) -> Tuple[float, bool]:
    """Retourne (somme patronale, au_moins_une_ligne_negative)."""
    sc = payslip_data.get("structure_cotisations") or {}
    if not isinstance(sc, dict):
        return 0.0, False
    lines = sc.get("cotisations") or []
    if not isinstance(lines, list):
        return 0.0, False
    s = 0.0
    neg = False
    for c in lines:
        if not isinstance(c, dict):
            continue
        mp = float(c.get("montant_patronal", 0) or 0)
        s += mp
        if mp < 0:
            neg = True
    return round(s, 2), neg


def _employee_context_from_row(
    row: Dict[str, Any],
    exits_by_employee: Dict[str, Dict[str, Any]],
) -> EmployeeAnomalyContext:
    emp = row.get("employees")
    if isinstance(emp, list) and emp:
        emp = emp[0]
    employment_status = ""
    if isinstance(emp, dict):
        employment_status = str(emp.get("employment_status") or "")
    employee_id = str(row.get("employee_id") or "")
    exit_row = exits_by_employee.get(employee_id) or {}
    return EmployeeAnomalyContext(
        employment_status=employment_status,
        exit_status=str(exit_row.get("status") or "") or None,
        last_working_day=parse_date_value(exit_row.get("last_working_day")),
    )


def _fetch_archived_exits_by_employee(
    company_id: str,
) -> Dict[str, Dict[str, Any]]:
    r = (
        supabase.table("employee_exits")
        .select("employee_id, status, last_working_day")
        .eq("company_id", company_id)
        .execute()
    )
    out: Dict[str, Dict[str, Any]] = {}
    for row in r.data or []:
        if not isinstance(row, dict):
            continue
        employee_id = str(row.get("employee_id") or "")
        if not employee_id:
            continue
        existing = out.get(employee_id)
        if existing is None or str(row.get("status") or "") == "archivee":
            out[employee_id] = row
    return out


def _dedupe_system_config_anomalies(
    anomalies: List[AnomaliePayslipItem],
) -> List[AnomaliePayslipItem]:
    seen: Set[Tuple[str, str]] = set()
    out: List[AnomaliePayslipItem] = []
    for item in anomalies:
        key = (item.type, item.message)
        if is_system_config_anomaly(item.type, item.valeur_detectee):
            if key in seen:
                continue
            seen.add(key)
        out.append(item)
    return out


def _collect_anomalies_for_row(
    row: Dict[str, Any],
    *,
    year: int,
    month: int,
    period_closed: bool,
    employee_ctx: EmployeeAnomalyContext,
    validation_workflow_active: bool = True,
) -> List[AnomaliePayslipItem]:
    payslip_id = str(row.get("id") or "")
    employee_id = str(row.get("employee_id") or "")
    emp = row.get("employees")
    employee_name = _employee_name(emp)
    pdata = row.get("payslip_data")
    status = str(row.get("status") or "brouillon")
    created_at = _parse_ts(row.get("created_at"))
    updated_at = _parse_ts(row.get("updated_at"))

    out: List[AnomaliePayslipItem] = []

    def _append(item: AnomaliePayslipItem) -> None:
        if should_include_anomaly_in_report(
            anomaly_type=item.type,
            severite=item.severite,
            payslip_status=status,
            period_closed=period_closed,
            employee_ctx=employee_ctx,
        ):
            out.append(item)

    if not isinstance(pdata, dict):
        _append(
            AnomaliePayslipItem(
                employee_id=employee_id,
                employee_name=employee_name,
                payslip_id=payslip_id,
                type="DONNEES_BULLETIN_INVALIDES",
                severite="bloquant",
                message="Structure payslip_data absente ou invalide.",
                valeur_detectee="—",
                suggestion_correction="Régénérer ou corriger le bulletin depuis l’éditeur paie.",
            )
        )
        return out

    brut = _to_float(pdata.get("salaire_brut"))
    net = _to_float(pdata.get("net_a_payer"))

    if brut < 0:
        _append(
            AnomaliePayslipItem(
                employee_id=employee_id,
                employee_name=employee_name,
                payslip_id=payslip_id,
                type="BRUT_NEGATIF",
                severite="bloquant",
                message="Salaire brut négatif.",
                valeur_detectee=f"{brut:.2f} €",
                suggestion_correction="Vérifier le calcul du brut et les lignes composantes.",
            )
        )
    elif brut == 0:
        _append(
            AnomaliePayslipItem(
                employee_id=employee_id,
                employee_name=employee_name,
                payslip_id=payslip_id,
                type="BRUT_NUL",
                severite="bloquant",
                message="Salaire brut nul.",
                valeur_detectee="0 €",
                suggestion_correction="Contrôler les heures / forfait jour et les saisies du mois.",
            )
        )

    if net > brut and brut >= 0:
        _append(
            AnomaliePayslipItem(
                employee_id=employee_id,
                employee_name=employee_name,
                payslip_id=payslip_id,
                type="NET_SUPERIEUR_BRUT",
                severite="avertissement",
                message=NET_SUPERIEUR_BRUT_MESSAGE,
                valeur_detectee=f"net={net:.2f} €, brut={brut:.2f} €",
                suggestion_correction="Contrôler cotisations, PAS, acomptes et net dans payslip_data.",
            )
        )

    heures = _sum_travail_base_hours(pdata.get("calcul_du_brut"))
    if heures > 0 and brut > 0:
        th = brut / heures
        if th < TAUX_HORAIRE_MIN or th > TAUX_HORAIRE_MAX:
            _append(
                AnomaliePayslipItem(
                    employee_id=employee_id,
                    employee_name=employee_name,
                    payslip_id=payslip_id,
                    type="TAUX_HORAIRE_INCOHERENT",
                    severite="avertissement",
                    message="Taux horaire effectif hors plage attendue.",
                    valeur_detectee=f"{th:.2f} €/h (brut {brut:.2f} € / {heures:.2f} h)",
                    suggestion_correction=(
                        f"Plage de référence : [{TAUX_HORAIRE_MIN:.2f} ; {TAUX_HORAIRE_MAX:.2f}] €/h "
                        f"(SMIC horaire 2024 = {SMIC_HORAIRE_2024} €)."
                    ),
                )
            )

    if brut > 0:
        primes = _sum_primes_from_brut(pdata.get("calcul_du_brut"))
        if primes > 0.5 * brut:
            _append(
                AnomaliePayslipItem(
                    employee_id=employee_id,
                    employee_name=employee_name,
                    payslip_id=payslip_id,
                    type="PRIMES_EXCESSIVES",
                    severite="avertissement",
                    message="Total des primes (lignes « prime ») supérieur à 50 % du brut.",
                    valeur_detectee=f"primes={primes:.2f} €, brut={brut:.2f} €",
                    suggestion_correction="Vérifier les saisies de primes et primes exceptionnelles.",
                )
            )

    tot_pat, any_neg_line = _sum_cotisations_patronales(pdata)
    if any_neg_line or tot_pat < 0:
        _append(
            AnomaliePayslipItem(
                employee_id=employee_id,
                employee_name=employee_name,
                payslip_id=payslip_id,
                type="COTISATIONS_PAT_NEGATIVES",
                severite="bloquant",
                message="Cotisation(s) patronale(s) négative(s) ou total patronal négatif.",
                valeur_detectee=f"total patronal agrégé={tot_pat:.2f} €",
                suggestion_correction="Contrôler structure_cotisations et rubriques exonérations / reprises.",
            )
        )

    # Sans circuit de validation utilisé sur le mois, « non validé » n'est pas une
    # anomalie : ce serait 100 % des bulletins signalés dès le 31ᵉ jour.
    if status != "valide" and validation_workflow_active:
        ref = created_at or updated_at
        now = datetime.now(timezone.utc)
        if ref and (now - ref) > timedelta(days=30):
            _append(
                AnomaliePayslipItem(
                    employee_id=employee_id,
                    employee_name=employee_name,
                    payslip_id=payslip_id,
                    type="DELAI_VALIDATION",
                    severite="avertissement",
                    message="Bulletin non validé depuis plus de 30 jours.",
                    valeur_detectee=f"statut={status}, créé le {ref.date().isoformat()}",
                    suggestion_correction="Valider ou régénérer le bulletin après contrôle RH.",
                )
            )

    for alerte in extraire_alertes_rh_depuis_bulletin(pdata):
        _append(
            AnomaliePayslipItem(
                employee_id=employee_id,
                employee_name=employee_name,
                payslip_id=payslip_id,
                type=f"ALERTE_{alerte['code'].upper()}",
                severite=alerte["severite"],
                message=alerte["message"],
                valeur_detectee=alerte.get("source") or "moteur_paie",
                suggestion_correction=(
                    "Ouvrir le bulletin, onglet Comparaison / alertes, "
                    "puis corriger la fiche salarié ou la convention collective."
                ),
            )
        )

    return out


def build_payslips_anomalies_report(
    company_id: str, year: int, month: int
) -> PayslipsAnomaliesReport:
    period_closed = payroll_analytics_repository.is_period_closed(
        company_id, year, month
    )
    exits_by_employee = _fetch_archived_exits_by_employee(company_id)

    r = (
        supabase.table("payslips")
        .select(
            "id, employee_id, payslip_data, status, created_at, updated_at, "
            "employees(first_name,last_name,employment_status)"
        )
        .eq("company_id", company_id)
        .eq("year", year)
        .eq("month", month)
        .execute()
    )
    rows: List[Dict[str, Any]] = list(r.data or [])
    validation_workflow_active = any(
        isinstance(row, dict) and str(row.get("status") or "") == "valide"
        for row in rows
    )
    anomalies: List[AnomaliePayslipItem] = []
    payslips_touchés: Set[str] = set()
    included_payslip_count = 0

    for row in rows:
        if not isinstance(row, dict):
            continue
        employee_ctx = _employee_context_from_row(row, exits_by_employee)
        if not should_include_payslip_in_anomalies_report(
            employee_ctx, year=year, month=month
        ):
            continue
        included_payslip_count += 1
        row_an = _collect_anomalies_for_row(
            row,
            year=year,
            month=month,
            period_closed=period_closed,
            employee_ctx=employee_ctx,
            validation_workflow_active=validation_workflow_active,
        )
        if row_an:
            payslips_touchés.add(str(row.get("id") or ""))
        anomalies.extend(row_an)

    anomalies = _dedupe_system_config_anomalies(anomalies)
    anomalies.sort(key=lambda a: (0 if a.severite == "bloquant" else 1, a.employee_name))

    return PayslipsAnomaliesReport(
        year=year,
        month=month,
        total_bulletins=included_payslip_count,
        bulletins_avec_anomalies=len(payslips_touchés),
        anomalies=anomalies,
    )

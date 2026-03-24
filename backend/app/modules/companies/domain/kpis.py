"""
Règles métier pures : calcul des KPIs entreprise.

Aucune I/O, aucun FastAPI. Utilisé par la couche application.
Comportement identique à l'ancien routeur (agrégations mensuelles, répartitions, etc.).
"""
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List


def compute_company_kpis(
    all_employees: List[Dict[str, Any]],
    payslips: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Calcule les KPIs dashboard à partir des données brutes (employees, payslips).
    Règle pure : pas d'accès DB ni à des services externes.
    """
    kpis: Dict[str, Any] = {}
    kpis["total_employees"] = len(all_employees)

    monthly_data = defaultdict(
        lambda: {
            "masse_salariale_brute": 0,
            "net_verse": 0,
            "charges_patronales": 0,
            "charges_salariales": 0,
            "cout_total_employeur": 0,
            "employee_count": 0,
        }
    )

    for payslip in payslips:
        month = payslip.get("month")
        year = payslip.get("year")
        payslip_data = payslip.get("payslip_data", {})

        if month is not None and year is not None and isinstance(payslip_data, dict):
            key = f"{year}-{month:02d}"

            remuneration = payslip_data.get("remuneration", {})
            brut = remuneration.get("brut", 0) or 0
            monthly_data[key]["masse_salariale_brute"] += brut

            net_a_payer = payslip_data.get("net_a_payer", 0) or 0
            monthly_data[key]["net_verse"] += net_a_payer

            cotisations = payslip_data.get("cotisations", [])
            for cotisation in cotisations:
                part_patronale = cotisation.get("part_patronale", 0) or 0
                part_salariale = cotisation.get("part_salariale", 0) or 0
                monthly_data[key]["charges_patronales"] += part_patronale
                monthly_data[key]["charges_salariales"] += part_salariale

            pied_de_page = payslip_data.get("pied_de_page", {})
            cout_employeur = pied_de_page.get("cout_total_employeur", 0) or 0
            monthly_data[key]["cout_total_employeur"] += cout_employeur
            monthly_data[key]["employee_count"] += 1

    today = date.today()
    last_month = today.replace(day=1) - timedelta(days=1)
    last_month_key = f"{last_month.year}-{last_month.month:02d}"
    current_month_key = f"{today.year}-{today.month:02d}"

    last_month_data = monthly_data.get(
        last_month_key,
        {
            "masse_salariale_brute": 0,
            "net_verse": 0,
            "charges_patronales": 0,
            "charges_salariales": 0,
            "cout_total_employeur": 0,
            "employee_count": 0,
        },
    )

    kpis["last_month_gross_salary"] = round(last_month_data["masse_salariale_brute"], 2)
    kpis["last_month_net_salary"] = round(last_month_data["net_verse"], 2)
    kpis["last_month_employer_charges"] = round(last_month_data["charges_patronales"], 2)
    kpis["last_month_employee_charges"] = round(last_month_data["charges_salariales"], 2)
    kpis["last_month_total_cost"] = round(last_month_data["cout_total_employeur"], 2)
    kpis["last_month_total_charges"] = round(
        last_month_data["charges_patronales"] + last_month_data["charges_salariales"], 2
    )

    sorted_months = sorted([k for k in monthly_data.keys() if k < current_month_key])[-12:]
    evolution_data = []
    for month_key in sorted_months:
        data = monthly_data[month_key]
        evolution_data.append({
            "month": month_key,
            "masse_salariale_brute": round(data["masse_salariale_brute"], 2),
            "net_verse": round(data["net_verse"], 2),
            "charges_totales": round(
                data["charges_patronales"] + data["charges_salariales"], 2
            ),
            "cout_total_employeur": round(data["cout_total_employeur"], 2),
        })
    kpis["evolution_12_months"] = evolution_data

    kpis["annual_gross_salary"] = round(
        sum(monthly_data[k]["masse_salariale_brute"] for k in sorted_months), 2
    )
    kpis["annual_total_cost"] = round(
        sum(monthly_data[k]["cout_total_employeur"] for k in sorted_months), 2
    )

    contract_distribution: Dict[str, int] = {}
    for employee in all_employees:
        ctype = employee.get("contract_type", "Non défini")
        contract_distribution[ctype] = contract_distribution.get(ctype, 0) + 1
    kpis["contract_distribution"] = contract_distribution

    job_distribution: Dict[str, int] = {}
    for employee in all_employees:
        job = employee.get("job_title", "Non défini")
        job_distribution[job] = job_distribution.get(job, 0) + 1
    kpis["job_distribution"] = job_distribution

    thirty_days_ago = (today - timedelta(days=30)).isoformat()
    new_hires = [
        e
        for e in all_employees
        if e.get("hire_date") and e.get("hire_date") >= thirty_days_ago
    ]
    kpis["new_hires_last_30_days"] = len(new_hires)

    if last_month_data["masse_salariale_brute"] > 0:
        kpis["payroll_tax_rate"] = round(
            (last_month_data["charges_patronales"] + last_month_data["charges_salariales"])
            / last_month_data["masse_salariale_brute"] * 100,
            2,
        )
    else:
        kpis["payroll_tax_rate"] = 0

    if kpis["total_employees"] > 0 and last_month_data["cout_total_employeur"] > 0:
        kpis["average_cost_per_employee"] = round(
            last_month_data["cout_total_employeur"]
            / last_month_data.get("employee_count", kpis["total_employees"]),
            2,
        )
    else:
        kpis["average_cost_per_employee"] = 0

    return kpis

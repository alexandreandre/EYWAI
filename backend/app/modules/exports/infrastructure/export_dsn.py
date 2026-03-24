# Implémentation locale du générateur DSN (ex-services.exports.dsn).
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from xml.dom import minidom

from app.core.database import supabase
from app.shared.utils.export import format_period


def validate_nir(nir: Optional[str]) -> Tuple[bool, Optional[str]]:
    if not nir:
        return False, "NIR manquant"
    nir_clean = nir.replace(" ", "").replace("-", "").replace(".", "")
    if len(nir_clean) != 15:
        return False, f"NIR invalide : doit contenir 15 chiffres (actuellement {len(nir_clean)})"
    if not nir_clean.isdigit():
        return False, "NIR invalide : doit contenir uniquement des chiffres"
    try:
        nir_digits = [int(d) for d in nir_clean[:13]]
        key = int(nir_clean[13:15])
        total = sum(nir_digits[i] * (2 if i % 2 == 0 else 1) for i in range(13))
        calculated_key = 97 - (total % 97)
        if calculated_key != key:
            return False, "NIR invalide : clé de contrôle incorrecte"
        return True, None
    except (ValueError, IndexError):
        return False, "NIR invalide : format incorrect"
    return True, None


def validate_siret(siret: Optional[str]) -> Tuple[bool, Optional[str]]:
    if not siret:
        return False, "SIRET manquant"
    siret_clean = siret.replace(" ", "").replace("-", "")
    if len(siret_clean) != 14:
        return False, f"SIRET invalide : doit contenir 14 chiffres (actuellement {len(siret_clean)})"
    if not siret_clean.isdigit():
        return False, "SIRET invalide : doit contenir uniquement des chiffres"

    def luhn_check(number: str) -> bool:
        digits = [int(d) for d in number]
        checksum = sum(
            d if i % 2 == 0 else (d * 2 if d < 5 else d * 2 - 9)
            for i, d in enumerate(reversed(digits))
        )
        return checksum % 10 == 0

    if not luhn_check(siret_clean):
        return False, "SIRET invalide : clé de contrôle incorrecte"
    return True, None


def get_company_data(company_id: str) -> Dict[str, Any]:
    response = supabase.table("companies").select("*").eq("id", company_id).single().execute()
    return response.data if response.data else {}


def get_dsn_employees_data(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    year, month = map(int, period.split("-"))

    query = supabase.table("employees").select(
        """
        id,
        first_name,
        last_name,
        nir,
        date_naissance,
        adresse,
        contract_type,
        hire_date,
        statut,
        company_id
        """
    ).eq("company_id", company_id)
    if employee_ids:
        query = query.in_("id", employee_ids)
    employees_response = query.execute()
    employees = employees_response.data or []

    payslips_query = supabase.table("payslips").select(
        """
        id,
        employee_id,
        month,
        year,
        payslip_data
        """
    ).eq("company_id", company_id).eq("year", year).eq("month", month)
    if employee_ids:
        payslips_query = payslips_query.in_("employee_id", employee_ids)
    payslips_response = payslips_query.execute()
    payslips = payslips_response.data or []
    payslips_by_employee = {p["employee_id"]: p for p in payslips}

    employees_data = []
    totals = {
        "nombre_salaries": 0,
        "nombre_contrats": 0,
        "masse_salariale_brute": 0.0,
        "total_charges": 0.0,
        "total_net_imposable": 0.0,
        "total_pas": 0.0,
        "total_cotisations_salariales": 0.0,
        "total_cotisations_patronales": 0.0,
    }

    for employee in employees:
        payslip = payslips_by_employee.get(employee["id"])
        if not payslip:
            continue
        payslip_data = payslip.get("payslip_data", {})
        if not isinstance(payslip_data, dict):
            continue
        brut = float(payslip_data.get("salaire_brut", 0) or 0)
        net_imposable = float(
            payslip_data.get("synthese_net", {}).get("net_imposable", 0)
            if isinstance(payslip_data.get("synthese_net"), dict)
            else 0
        )
        pas = float(
            payslip_data.get("synthese_net", {}).get("impot_preleve_a_la_source", 0)
            if isinstance(payslip_data.get("synthese_net"), dict)
            else 0
        )
        cotisations = payslip_data.get("structure_cotisations", {})
        cotisations_list = (
            cotisations.get("cotisations", []) if isinstance(cotisations, dict) else []
        )
        cotisations_salariales = sum(
            float(c.get("montant_salarial", 0) or 0)
            for c in cotisations_list
            if isinstance(c, dict)
        )
        cotisations_patronales = sum(
            float(c.get("montant_patronal", 0) or 0)
            for c in cotisations_list
            if isinstance(c, dict)
        )
        employees_data.append({
            "employee": employee,
            "payslip": payslip,
            "brut": brut,
            "net_imposable": net_imposable,
            "pas": pas,
            "cotisations_salariales": cotisations_salariales,
            "cotisations_patronales": cotisations_patronales,
            "cotisations_detail": cotisations_list,
        })
        totals["nombre_salaries"] += 1
        totals["nombre_contrats"] += 1
        totals["masse_salariale_brute"] += brut
        totals["total_charges"] += cotisations_salariales + cotisations_patronales
        totals["total_net_imposable"] += net_imposable
        totals["total_pas"] += pas
        totals["total_cotisations_salariales"] += cotisations_salariales
        totals["total_cotisations_patronales"] += cotisations_patronales

    return employees_data, totals


def check_dsn_data(
    company_id: str,
    period: str,
    employees_data: List[Dict[str, Any]],
    company_data: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    anomalies = []
    warnings = []

    siret = company_data.get("siret")
    siret_valid, siret_error = validate_siret(siret)
    if not siret_valid:
        anomalies.append({
            "type": "error",
            "message": f"SIRET établissement : {siret_error}",
            "severity": "blocking",
            "employee_id": None,
            "employee_name": None,
        })
    code_naf = company_data.get("code_naf")
    if not code_naf:
        anomalies.append({
            "type": "error",
            "message": "Code NAF manquant pour l'établissement",
            "severity": "blocking",
            "employee_id": None,
            "employee_name": None,
        })
    address = company_data.get("address")
    if not address or not isinstance(address, dict):
        warnings.append("Adresse établissement incomplète")
    else:
        if (
            not address.get("rue")
            or not address.get("ville")
            or not address.get("code_postal")
        ):
            warnings.append(
                "Adresse établissement incomplète (rue, ville ou code postal manquant)"
            )

    for emp_data in employees_data:
        employee = emp_data["employee"]
        employee_id = employee.get("id")
        employee_name = (
            f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip()
        )
        nir = employee.get("nir")
        nir_valid, nir_error = validate_nir(nir)
        if not nir_valid:
            anomalies.append({
                "type": "error",
                "message": f"Salarié {employee_name} : {nir_error}",
                "severity": "blocking",
                "employee_id": employee_id,
                "employee_name": employee_name,
            })
        contract_type = employee.get("contract_type")
        if not contract_type:
            anomalies.append({
                "type": "error",
                "message": f"Salarié {employee_name} : type de contrat manquant",
                "severity": "blocking",
                "employee_id": employee_id,
                "employee_name": employee_name,
            })
        adresse = employee.get("adresse")
        if not adresse or not isinstance(adresse, dict):
            warnings.append(f"Salarié {employee_name} : adresse incomplète")
        else:
            if (
                not adresse.get("rue")
                or not adresse.get("ville")
                or not adresse.get("code_postal")
            ):
                warnings.append(f"Salarié {employee_name} : adresse incomplète")
        brut = emp_data.get("brut", 0)
        net_imposable = emp_data.get("net_imposable", 0)
        if brut <= 0:
            anomalies.append({
                "type": "error",
                "message": f"Salarié {employee_name} : brut ≤ 0",
                "severity": "blocking",
                "employee_id": employee_id,
                "employee_name": employee_name,
            })
        if net_imposable > brut:
            anomalies.append({
                "type": "error",
                "message": f"Salarié {employee_name} : net imposable > brut (incohérence)",
                "severity": "blocking",
                "employee_id": employee_id,
                "employee_name": employee_name,
            })
        specificites = employee.get("specificites_paie", {})
        if isinstance(specificites, dict):
            mutuelle = specificites.get("mutuelle", {})
            prevoyance = specificites.get("prevoyance", {})
            if contract_type in ["CDI", "CDD"] and not mutuelle.get("adhesion"):
                warnings.append(
                    f"Salarié {employee_name} : mutuelle absente alors que contrat actif"
                )
            if contract_type in ["CDI", "CDD"] and not prevoyance.get("adhesion"):
                warnings.append(
                    f"Salarié {employee_name} : prévoyance absente alors que contrat actif"
                )
        hire_date = employee.get("hire_date")
        if hire_date:
            try:
                year, month = map(int, period.split("-"))
                hire_dt = (
                    datetime.strptime(hire_date, "%Y-%m-%d")
                    if isinstance(hire_date, str)
                    else hire_date
                )
                period_dt = datetime(year, month, 1)
                if hire_dt.month == period_dt.month and hire_dt.year == period_dt.year:
                    warnings.append(
                        f"Salarié {employee_name} : entré en cours de mois ({hire_date})"
                    )
            except Exception:
                pass

    return anomalies, warnings


def preview_dsn(
    company_id: str,
    period: str,
    dsn_type: str,
    employee_ids: Optional[List[str]] = None,
    establishment_id: Optional[str] = None,
) -> Dict[str, Any]:
    company_data = get_company_data(company_id)
    employees_data, totals = get_dsn_employees_data(company_id, period, employee_ids)
    anomalies, warnings = check_dsn_data(
        company_id, period, employees_data, company_data
    )

    employees_preview = []
    for emp_data in employees_data:
        employee = emp_data["employee"]
        cotisations_detail = emp_data.get("cotisations_detail", [])
        organismes = set()
        for coti in cotisations_detail:
            if isinstance(coti, dict):
                libelle = coti.get("libelle", "")
                if "URSSAF" in libelle.upper():
                    organismes.add("URSSAF")
                elif (
                    "RETRAITE" in libelle.upper()
                    or "AGIRC" in libelle.upper()
                    or "ARRCO" in libelle.upper()
                ):
                    organismes.add("RETRAITE")
                elif "PREVOYANCE" in libelle.upper():
                    organismes.add("PREVOYANCE")
                elif "MUTUELLE" in libelle.upper():
                    organismes.add("MUTUELLE")
        employees_preview.append({
            "employee_id": employee.get("id"),
            "nom": employee.get("last_name", ""),
            "prenom": employee.get("first_name", ""),
            "nir": employee.get("nir"),
            "contrat_type": employee.get("contract_type"),
            "brut": emp_data.get("brut", 0),
            "net_imposable": emp_data.get("net_imposable", 0),
            "pas": emp_data.get("pas", 0),
            "cotisations_salariales": emp_data.get("cotisations_salariales", 0),
            "cotisations_patronales": emp_data.get("cotisations_patronales", 0),
            "organismes": list(organismes),
        })

    organismes_summary = {}
    for emp_data in employees_data:
        cotisations_detail = emp_data.get("cotisations_detail", [])
        for coti in cotisations_detail:
            if isinstance(coti, dict):
                libelle = coti.get("libelle", "")
                organisme = "AUTRE"
                if "URSSAF" in libelle.upper():
                    organisme = "URSSAF"
                elif (
                    "RETRAITE" in libelle.upper()
                    or "AGIRC" in libelle.upper()
                    or "ARRCO" in libelle.upper()
                ):
                    organisme = "RETRAITE"
                elif "PREVOYANCE" in libelle.upper():
                    organisme = "PREVOYANCE"
                elif "MUTUELLE" in libelle.upper():
                    organisme = "MUTUELLE"
                if organisme not in organismes_summary:
                    organismes_summary[organisme] = {
                        "organisme": organisme,
                        "code_organisme": None,
                        "nombre_salaries": set(),
                        "total_cotisations_salariales": 0.0,
                        "total_cotisations_patronales": 0.0,
                    }
                organismes_summary[organisme]["nombre_salaries"].add(
                    emp_data["employee"]["id"]
                )
                organismes_summary[organisme]["total_cotisations_salariales"] += float(
                    coti.get("montant_salarial", 0) or 0
                )
                organismes_summary[organisme]["total_cotisations_patronales"] += float(
                    coti.get("montant_patronal", 0) or 0
                )

    organismes_list = [
        {
            "organisme": org["organisme"],
            "code_organisme": org["code_organisme"],
            "nombre_salaries": len(org["nombre_salaries"]),
            "total_cotisations_salariales": org["total_cotisations_salariales"],
            "total_cotisations_patronales": org["total_cotisations_patronales"],
        }
        for org in organismes_summary.values()
    ]

    return {
        "period": period,
        "dsn_type": dsn_type,
        "establishment_siret": company_data.get("siret"),
        "nombre_salaries": totals["nombre_salaries"],
        "nombre_contrats": totals["nombre_contrats"],
        "masse_salariale_brute": totals["masse_salariale_brute"],
        "total_charges": totals["total_charges"],
        "total_net_imposable": totals["total_net_imposable"],
        "total_pas": totals["total_pas"],
        "organismes_concernes": organismes_list,
        "employees_preview": employees_preview,
        "anomalies": anomalies,
        "warnings": warnings,
        "can_generate": len([a for a in anomalies if a.get("severity") == "blocking"])
        == 0,
    }


def generate_dsn_xml(
    company_id: str,
    period: str,
    dsn_type: str,
    employee_ids: Optional[List[str]] = None,
    establishment_id: Optional[str] = None,
) -> bytes:
    company_data = get_company_data(company_id)
    employees_data, totals = get_dsn_employees_data(
        company_id, period, employee_ids
    )
    year, month = map(int, period.split("-"))

    root = ET.Element("DSN")
    root.set("xmlns", "http://www.dsn.fr/dsn")
    root.set("version", "01.00")

    header = ET.SubElement(root, "EnTeteDSN")
    ET.SubElement(header, "TypeDSN").text = "01"
    ET.SubElement(header, "DateEnvoi").text = datetime.now().strftime("%Y-%m-%d")
    ET.SubElement(header, "PeriodeDeclaree").text = period

    etablissement = ET.SubElement(root, "Etablissement")
    ET.SubElement(etablissement, "SIRET").text = company_data.get("siret", "")
    ET.SubElement(etablissement, "CodeNAF").text = company_data.get("code_naf", "")
    address = company_data.get("address", {})
    if isinstance(address, dict):
        adresse_etab = ET.SubElement(etablissement, "Adresse")
        ET.SubElement(adresse_etab, "Rue").text = address.get("rue", "")
        ET.SubElement(adresse_etab, "CodePostal").text = address.get("code_postal", "")
        ET.SubElement(adresse_etab, "Ville").text = address.get("ville", "")

    salaries = ET.SubElement(root, "Salaries")
    for emp_data in employees_data:
        employee = emp_data["employee"]
        payslip_data = emp_data["payslip"].get("payslip_data", {})

        salarie = ET.SubElement(salaries, "Salarie")
        identite = ET.SubElement(salarie, "Identite")
        ET.SubElement(identite, "Nom").text = employee.get("last_name", "")
        ET.SubElement(identite, "Prenom").text = employee.get("first_name", "")
        ET.SubElement(identite, "NIR").text = employee.get("nir", "")
        contrat = ET.SubElement(salarie, "Contrat")
        ET.SubElement(contrat, "TypeContrat").text = employee.get("contract_type", "")
        ET.SubElement(contrat, "DateEntree").text = employee.get("hire_date", "")
        remuneration = ET.SubElement(salarie, "Remuneration")
        ET.SubElement(remuneration, "Brut").text = str(emp_data.get("brut", 0))
        ET.SubElement(remuneration, "NetImposable").text = str(
            emp_data.get("net_imposable", 0)
        )
        ET.SubElement(remuneration, "PAS").text = str(emp_data.get("pas", 0))
        cotisations = ET.SubElement(salarie, "Cotisations")
        for coti in emp_data.get("cotisations_detail", []):
            if isinstance(coti, dict):
                cotisation = ET.SubElement(cotisations, "Cotisation")
                ET.SubElement(cotisation, "Libelle").text = coti.get("libelle", "")
                ET.SubElement(cotisation, "Base").text = str(coti.get("base", 0))
                ET.SubElement(cotisation, "TauxSalarial").text = str(
                    coti.get("taux_salarial", 0) or 0
                )
                ET.SubElement(cotisation, "TauxPatronal").text = str(
                    coti.get("taux_patronal", 0) or 0
                )
                ET.SubElement(cotisation, "MontantSalarial").text = str(
                    coti.get("montant_salarial", 0) or 0
                )
                ET.SubElement(cotisation, "MontantPatronal").text = str(
                    coti.get("montant_patronal", 0) or 0
                )

    xml_string = ET.tostring(root, encoding="unicode")
    dom = minidom.parseString(xml_string)
    pretty_xml = dom.toprettyxml(indent="  ", encoding="utf-8")
    return pretty_xml

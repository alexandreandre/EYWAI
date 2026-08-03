# Générateur DSN mensuelle NEODeS P26V01 (fichier plat).
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import supabase
from app.modules.dsn_export.application.builder import (
    DsnBuildError,
    build_parsed_dsn_from_payroll,
)
from app.modules.dsn_export.domain.writer import encode_dsn_bytes
from app.modules.dsn_import.domain.parser import parse_dsn_content
from app.modules.dsn_import.domain.validation import validate_parsed_dsn
from app.modules.exports.infrastructure.payslip_accounting_extract import (
    extract_cotisations_from_payslip,
    extract_pas_amount,
)
from app.modules.oeth_settings.application import queries as oeth_queries
from app.shared.dsn_validation import validate_nir, validate_nir_dsn, validate_siret

DSN_NORME = "P26V01"


def get_company_data(company_id: str) -> Dict[str, Any]:
    response = (
        supabase.table("companies").select("*").eq("id", company_id).single().execute()
    )
    data = response.data if response.data else {}
    if not data:
        return {}
    # Normalise les alias attendus par le builder P26
    if not data.get("name"):
        data["name"] = data.get("company_name") or data.get("raison_sociale") or ""
    if not data.get("address") or not isinstance(data.get("address"), dict):
        data["address"] = {
            "rue": data.get("adresse_rue") or "",
            "code_postal": data.get("adresse_code_postal") or "",
            "ville": data.get("adresse_ville") or "",
        }
    if not data.get("code_naf"):
        data["code_naf"] = data.get("naf_ape") or ""
    return data


def get_dsn_employees_data(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    year, month = map(int, period.split("-"))

    query = (
        supabase.table("employees")
        .select(
            """
        id,
        first_name,
        last_name,
        nir,
        sexe,
        date_naissance,
        lieu_naissance,
        adresse,
        contract_type,
        hire_date,
        statut,
        company_id,
        specificites_paie,
        matricule,
        job_title,
        is_temps_partiel,
        duree_hebdomadaire,
        classification_conventionnelle,
        nom_usage,
        nationalite,
        is_forfait_jour,
        contract_end_date,
        employment_status
        """
        )
        .eq("company_id", company_id)
    )
    if employee_ids:
        query = query.in_("id", employee_ids)
    employees_response = query.execute()
    employees = employees_response.data or []

    payslips_query = (
        supabase.table("payslips")
        .select(
            """
        id,
        employee_id,
        month,
        year,
        payslip_data
        """
        )
        .eq("company_id", company_id)
        .eq("year", year)
        .eq("month", month)
    )
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
        # Enrichissements DSN absents en colonnes natives
        if not employee.get("idcc"):
            employee["idcc"] = ""
        classif = employee.get("classification_conventionnelle")
        if isinstance(classif, dict):
            employee.setdefault("pcs", classif.get("pcs") or classif.get("code_pcs") or "")
            employee.setdefault(
                "idcc", classif.get("idcc") or employee.get("idcc") or ""
            )
        brut = float(payslip_data.get("salaire_brut", 0) or 0)
        synthese = payslip_data.get("synthese_net")
        net_imposable = float(
            synthese.get("net_imposable", 0) if isinstance(synthese, dict) else 0
        )
        pas = extract_pas_amount(synthese) if isinstance(synthese, dict) else 0.0
        cot_sal, cot_pat, cotisations_list, _meta = extract_cotisations_from_payslip(
            payslip_data
        )
        # Enrichissement BOETH pour le builder
        try:
            boeth = oeth_queries.get_boeth_code_for_employee(employee.get("id", ""), period)
            if boeth:
                employee = {**employee, "boeth_code": boeth}
        except Exception:
            pass
        employees_data.append(
            {
                "employee": employee,
                "payslip": payslip,
                "payslip_data": payslip_data,
                "brut": brut,
                "net_imposable": net_imposable,
                "pas": pas,
                "cotisations_salariales": cot_sal,
                "cotisations_patronales": cot_pat,
                "cotisations_detail": cotisations_list,
            }
        )
        totals["nombre_salaries"] += 1
        totals["nombre_contrats"] += 1
        totals["masse_salariale_brute"] += brut
        totals["total_charges"] += cot_sal + cot_pat
        totals["total_net_imposable"] += net_imposable
        totals["total_pas"] += pas
        totals["total_cotisations_salariales"] += cot_sal
        totals["total_cotisations_patronales"] += cot_pat

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
        anomalies.append(
            {
                "type": "error",
                "message": f"SIRET établissement : {siret_error}",
                "severity": "blocking",
                "employee_id": None,
                "employee_name": None,
            }
        )
    code_naf = company_data.get("code_naf")
    if not code_naf:
        anomalies.append(
            {
                "type": "error",
                "message": "Code NAF manquant pour l'établissement",
                "severity": "blocking",
                "employee_id": None,
                "employee_name": None,
            }
        )
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
        nir_valid, nir_error = validate_nir_dsn(nir)
        if not nir_valid:
            anomalies.append(
                {
                    "type": "error",
                    "message": f"Salarié {employee_name} : {nir_error}",
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": employee_name,
                }
            )
        contract_type = employee.get("contract_type")
        if not contract_type:
            anomalies.append(
                {
                    "type": "error",
                    "message": f"Salarié {employee_name} : type de contrat manquant",
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": employee_name,
                }
            )
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
            anomalies.append(
                {
                    "type": "error",
                    "message": f"Salarié {employee_name} : brut ≤ 0",
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": employee_name,
                }
            )
        if net_imposable > brut:
            anomalies.append(
                {
                    "type": "error",
                    "message": f"Salarié {employee_name} : net imposable > brut (incohérence)",
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": employee_name,
                }
            )
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
        employees_preview.append(
            {
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
            }
        )

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


def _neodes_norme_version() -> str:
    return DSN_NORME


def generate_dsn_file(
    company_id: str,
    period: str,
    dsn_type: str,
    employee_ids: Optional[List[str]] = None,
    establishment_id: Optional[str] = None,
) -> bytes:
    """Génère un fichier DSN plat P26V01, relu et validé avant retour."""
    company_data = get_company_data(company_id)
    if establishment_id:
        # Filtre multi-établissement : si la fiche société expose des établissements
        establishments = company_data.get("establishments") or []
        if isinstance(establishments, list):
            for etab in establishments:
                if isinstance(etab, dict) and str(etab.get("id")) == str(establishment_id):
                    company_data = {
                        **company_data,
                        "siret": etab.get("siret") or company_data.get("siret"),
                        "code_naf": etab.get("code_naf") or company_data.get("code_naf"),
                        "address": etab.get("address") or company_data.get("address"),
                        "name": etab.get("name") or company_data.get("name"),
                    }
                    break

    employees_data, _totals = get_dsn_employees_data(company_id, period, employee_ids)
    period_formatted = period.replace("-", "_")
    file_name = f"dsn_mensuelle_{period_formatted}.dsn"
    try:
        dsn_file, build_warnings = build_parsed_dsn_from_payroll(
            company_data,
            employees_data,
            period,
            dsn_type=dsn_type,
            file_name=file_name,
            require_cotisation_codes=False,
        )
    except DsnBuildError as exc:
        raise ValueError(str(exc)) from exc

    # OETH annuelle (avril) : codes BOETH déjà injectés via get_dsn_employees_data ;
    # les totaux établissement OETH restent en avertissement si absents du modèle plat.
    year, month = map(int, period.split("-"))
    if month == 4:
        try:
            dsn_oeth = oeth_queries.build_dsn_payload(company_id, year - 1)
            if dsn_oeth.complement_oeth or dsn_oeth.cotisations_etablissement:
                build_warnings.append(
                    "Compléments OETH disponibles : vérifier le dépôt annuel complémentaire."
                )
        except Exception:
            pass

    content = encode_dsn_bytes(dsn_file)
    # Relecture + validation structurelle
    parsed = parse_dsn_content(content, file_name=file_name)
    if parsed.envoi.norme != DSN_NORME:
        raise ValueError(f"Norme DSN inattendue après génération : {parsed.envoi.norme}")
    from app.modules.dsn_import.domain.model import ParsedDsnSet

    anomalies = validate_parsed_dsn(ParsedDsnSet(files=[parsed], warnings=list(build_warnings)))
    blocking = [a for a in anomalies if a.get("severity") == "blocking"]
    if blocking:
        messages = "; ".join(a.get("message", "") for a in blocking[:5])
        raise ValueError(f"DSN générée invalide : {messages}")
    return content


def generate_dsn_xml(
    company_id: str,
    period: str,
    dsn_type: str,
    employee_ids: Optional[List[str]] = None,
    establishment_id: Optional[str] = None,
) -> bytes:
    """Alias historique : produit désormais un fichier plat P26V01 (.dsn)."""
    return generate_dsn_file(
        company_id, period, dsn_type, employee_ids, establishment_id
    )

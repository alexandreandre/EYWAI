# Délégation vers les implémentations locales des générateurs d'export (infrastructure du module).
# Plus aucune dépendance vers services/exports/*.
from typing import Any, Dict, List, Optional, Tuple

from .export_dsn import (
    generate_dsn_xml as _generate_dsn_xml,
    get_company_data as _get_company_data,
    get_dsn_employees_data as _get_dsn_employees_data,
    preview_dsn as _preview_dsn,
)
from .export_ecritures_comptables import (
    generate_od_charges_sociales as _generate_od_charges_sociales,
    generate_od_export_file as _generate_od_export_file,
    generate_od_pas as _generate_od_pas,
    generate_od_salaires as _generate_od_salaires,
    get_payslip_data_for_od as _get_payslip_data_for_od,
    preview_od as _preview_od,
)
from .export_formats_cabinet import (
    generate_cabinet_generic_export as _generate_cabinet_generic_export,
    generate_cabinet_quadra_export as _generate_cabinet_quadra_export,
    generate_cabinet_sage_export as _generate_cabinet_sage_export,
    preview_cabinet_export as _preview_cabinet_export,
)
from .export_journal_paie import (
    generate_journal_paie_export as _generate_journal_paie_export,
    get_journal_paie_data as _get_journal_paie_data,
    preview_journal_paie as _preview_journal_paie,
)
from .export_paiement_salaires import (
    generate_bank_file as _generate_bank_file,
    generate_paiement_salaires_export as _generate_paiement_salaires_export,
    get_paiement_salaires_data as _get_paiement_salaires_data,
    preview_paiement_salaires as _preview_paiement_salaires,
)


def preview_journal_paie(
    company_id: str, period: str, employee_ids: Optional[List[str]]
) -> Dict[str, Any]:
    return _preview_journal_paie(company_id, period, employee_ids)


def generate_journal_paie_export(
    company_id: str, period: str, employee_ids: Optional[List[str]], format: str
) -> bytes:
    return _generate_journal_paie_export(company_id, period, employee_ids, format)


def get_journal_paie_data(
    company_id: str, period: str, employee_ids: Optional[List[str]]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    return _get_journal_paie_data(company_id, period, employee_ids)


def preview_paiement_salaires(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    excluded_employee_ids: Optional[List[str]],
    execution_date: Optional[str],
    payment_label: Optional[str],
) -> Dict[str, Any]:
    return _preview_paiement_salaires(
        company_id,
        period,
        employee_ids,
        excluded_employee_ids,
        execution_date,
        payment_label,
    )


def generate_paiement_salaires_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    excluded_employee_ids: Optional[List[str]],
    execution_date: Optional[str],
    payment_label: Optional[str],
    format: str,
) -> bytes:
    return _generate_paiement_salaires_export(
        company_id,
        period,
        employee_ids,
        excluded_employee_ids,
        execution_date,
        payment_label,
        format,
    )


def generate_bank_file(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    excluded_employee_ids: Optional[List[str]],
    execution_date: Optional[str],
    payment_label: Optional[str],
) -> bytes:
    return _generate_bank_file(
        company_id,
        period,
        employee_ids,
        excluded_employee_ids,
        execution_date,
        payment_label,
    )


def get_paiement_salaires_data(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    excluded_employee_ids: Optional[List[str]],
    execution_date: Optional[str],
    payment_label: Optional[str],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]], List[str]]:
    return _get_paiement_salaires_data(
        company_id,
        period,
        employee_ids,
        excluded_employee_ids,
        execution_date,
        payment_label,
    )


def preview_od(
    company_id: str,
    period: str,
    export_type: str,
    employee_ids: Optional[List[str]],
    date_ecriture: Optional[str],
) -> Dict[str, Any]:
    return _preview_od(company_id, period, export_type, employee_ids, date_ecriture)


def generate_od_salaires(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    date_ecriture: Optional[str],
):
    return _generate_od_salaires(company_id, period, employee_ids, date_ecriture)


def generate_od_charges_sociales(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    date_ecriture: Optional[str],
):
    return _generate_od_charges_sociales(
        company_id, period, employee_ids, date_ecriture
    )


def generate_od_pas(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    date_ecriture: Optional[str],
):
    return _generate_od_pas(company_id, period, employee_ids, date_ecriture)


def generate_od_export_file(
    ecritures: List[Dict[str, Any]], export_type: str, period: str, format: str
) -> bytes:
    return _generate_od_export_file(ecritures, export_type, period, format)


def get_payslip_data_for_od(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    od_type: str = "od_salaires",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    return _get_payslip_data_for_od(company_id, period, employee_ids, od_type)


def preview_cabinet_export(
    company_id: str, period: str, export_type: str, employee_ids: Optional[List[str]]
) -> Dict[str, Any]:
    return _preview_cabinet_export(company_id, period, export_type, employee_ids)


def generate_cabinet_generic_export(
    company_id: str, period: str, employee_ids: Optional[List[str]], format: str
) -> bytes:
    return _generate_cabinet_generic_export(company_id, period, employee_ids, format)


def generate_cabinet_quadra_export(
    company_id: str, period: str, employee_ids: Optional[List[str]], format: str
) -> bytes:
    return _generate_cabinet_quadra_export(company_id, period, employee_ids, format)


def generate_cabinet_sage_export(
    company_id: str, period: str, employee_ids: Optional[List[str]], format: str
) -> bytes:
    return _generate_cabinet_sage_export(company_id, period, employee_ids, format)


def preview_dsn(
    company_id: str,
    period: str,
    dsn_type: str,
    employee_ids: Optional[List[str]],
    establishment_id: Optional[str],
) -> Dict[str, Any]:
    return _preview_dsn(company_id, period, dsn_type, employee_ids, establishment_id)


def generate_dsn_xml(
    company_id: str,
    period: str,
    dsn_type: str,
    employee_ids: Optional[List[str]],
    establishment_id: Optional[str],
) -> bytes:
    return _generate_dsn_xml(
        company_id, period, dsn_type, employee_ids, establishment_id
    )


def get_dsn_employees_data(
    company_id: str, period: str, employee_ids: Optional[List[str]]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    return _get_dsn_employees_data(company_id, period, employee_ids)


def get_company_data(company_id: str) -> Dict[str, Any]:
    return _get_company_data(company_id)

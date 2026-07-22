# Délégation vers les implémentations locales des générateurs d'export (infrastructure du module).
# Plus aucune dépendance vers services/exports/*.
from typing import Any, Dict, List, Optional, Tuple

from .export_dsn import (
    generate_dsn_file as _generate_dsn_file,
    generate_dsn_xml as _generate_dsn_xml,
    get_company_data as _get_company_data,
    get_dsn_employees_data as _get_dsn_employees_data,
    preview_dsn as _preview_dsn,
)
from .export_ecritures_comptables import (
    generate_od_charges_sociales as _generate_od_charges_sociales,
    generate_od_export_file as _generate_od_export_file,
    generate_od_globale as _generate_od_globale,
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
from .export_charges_sociales import (
    generate_charges_sociales_export as _generate_charges_sociales_export,
    preview_charges_sociales as _preview_charges_sociales,
)
from .export_notes_frais import (
    generate_notes_frais_export as _generate_notes_frais_export,
    preview_notes_frais as _preview_notes_frais,
)
from .export_acomptes import (
    generate_acomptes_ecritures_export as _generate_acomptes_ecritures_export,
    generate_acomptes_export as _generate_acomptes_export,
    preview_acomptes as _preview_acomptes,
)
from .export_saisies import (
    generate_saisies_ecritures_export as _generate_saisies_ecritures_export,
    generate_saisies_export as _generate_saisies_export,
    preview_saisies as _preview_saisies,
)
from .export_fec import generate_fec_export as _generate_fec_export, preview_fec as _preview_fec
from .export_sepa import generate_sepa_pain001 as _generate_sepa_pain001
from .export_paiement_organismes import (
    generate_paiement_organismes_export as _generate_paiement_organismes_export,
    preview_paiement_organismes as _preview_paiement_organismes,
)
from .export_prets_employeur import (
    generate_prets_employeur_export as _generate_prets_employeur_export,
    preview_prets_employeur as _preview_prets_employeur,
)
from .export_attestations import (
    generate_attestations_export as _generate_attestations_export,
    preview_attestations as _preview_attestations,
)
from .export_conges_absences import (
    generate_conges_absences_export as _generate_conges_absences_export,
    preview_conges_absences as _preview_conges_absences,
)
from .export_recapitulatif_montants import (
    generate_recapitulatif_montants_export as _generate_recapitulatif_montants_export,
    preview_recapitulatif_montants as _preview_recapitulatif_montants,
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


def preview_charges_sociales(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    caisses: Optional[List[str]] = None,
    include_consolidated: bool = True,
) -> Dict[str, Any]:
    return _preview_charges_sociales(
        company_id,
        period,
        employee_ids,
        caisses,
        include_consolidated,
    )


def generate_charges_sociales_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    format: str,
    caisses: Optional[List[str]] = None,
    include_consolidated: bool = True,
) -> bytes:
    return _generate_charges_sociales_export(
        company_id,
        period,
        employee_ids,
        format,
        caisses,
        include_consolidated,
    )


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
    regroupement: str = "global",
) -> Dict[str, Any]:
    return _preview_od(
        company_id, period, export_type, employee_ids, date_ecriture, regroupement
    )


def generate_od_salaires(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    date_ecriture: Optional[str],
    regroupement: str = "global",
):
    return _generate_od_salaires(
        company_id, period, employee_ids, date_ecriture, regroupement
    )


def generate_od_charges_sociales(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    date_ecriture: Optional[str],
    regroupement: str = "global",
):
    return _generate_od_charges_sociales(
        company_id, period, employee_ids, date_ecriture, regroupement
    )


def generate_od_pas(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    date_ecriture: Optional[str],
    regroupement: str = "global",
):
    return _generate_od_pas(
        company_id, period, employee_ids, date_ecriture, regroupement
    )


def generate_od_globale(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    date_ecriture: Optional[str],
    regroupement: str = "global",
):
    return _generate_od_globale(
        company_id, period, employee_ids, date_ecriture, regroupement
    )


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


def preview_notes_frais(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    expense_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return _preview_notes_frais(company_id, period, employee_ids, expense_types)


def generate_notes_frais_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    file_format: str,
    cabinet_format: str = "generique",
    expense_types: Optional[List[str]] = None,
) -> bytes:
    return _generate_notes_frais_export(
        company_id,
        period,
        employee_ids,
        file_format,
        cabinet_format,  # type: ignore[arg-type]
        expense_types,
    )


def preview_conges_absences(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    absence_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return _preview_conges_absences(
        company_id, period, employee_ids, absence_types
    )


def generate_conges_absences_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    file_format: str,
    absence_types: Optional[List[str]] = None,
) -> bytes:
    return _generate_conges_absences_export(
        company_id, period, employee_ids, file_format, absence_types
    )


def preview_recapitulatif_montants(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    excluded_employee_ids: Optional[List[str]] = None,
    execution_date: Optional[str] = None,
    payment_label: Optional[str] = None,
) -> Dict[str, Any]:
    return _preview_recapitulatif_montants(
        company_id,
        period,
        employee_ids,
        excluded_employee_ids,
        execution_date,
        payment_label,
    )


def generate_recapitulatif_montants_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]],
    excluded_employee_ids: Optional[List[str]],
    execution_date: Optional[str],
    payment_label: Optional[str],
    file_format: str,
) -> bytes:
    return _generate_recapitulatif_montants_export(
        company_id,
        period,
        employee_ids,
        excluded_employee_ids,
        execution_date,
        payment_label,
        file_format,
    )


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


def generate_dsn_file(
    company_id: str,
    period: str,
    dsn_type: str,
    employee_ids: Optional[List[str]],
    establishment_id: Optional[str],
) -> bytes:
    return _generate_dsn_file(
        company_id, period, dsn_type, employee_ids, establishment_id
    )


def get_dsn_employees_data(
    company_id: str, period: str, employee_ids: Optional[List[str]]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    return _get_dsn_employees_data(company_id, period, employee_ids)


def get_company_data(company_id: str) -> Dict[str, Any]:
    return _get_company_data(company_id)


def preview_acomptes(company_id: str, period: str) -> Dict[str, Any]:
    return _preview_acomptes(company_id, period)


def generate_acomptes_export(
    company_id: str, period: str, file_format: str
) -> bytes:
    return _generate_acomptes_export(company_id, period, file_format)


def generate_acomptes_ecritures_export(
    company_id: str, period: str, file_format: str
) -> bytes:
    return _generate_acomptes_ecritures_export(company_id, period, file_format)


def preview_saisies(company_id: str, period: str) -> Dict[str, Any]:
    return _preview_saisies(company_id, period)


def generate_saisies_export(
    company_id: str, period: str, file_format: str
) -> bytes:
    return _generate_saisies_export(company_id, period, file_format)


def generate_saisies_ecritures_export(
    company_id: str, period: str, file_format: str
) -> bytes:
    return _generate_saisies_ecritures_export(company_id, period, file_format)


def preview_fec(company_id: str, period: str, employee_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    return _preview_fec(company_id, period, employee_ids)


def generate_fec_export(
    company_id: str, period: str, employee_ids: Optional[List[str]] = None
) -> bytes:
    return _generate_fec_export(company_id, period, employee_ids)


def generate_sepa_bank_file(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    excluded_employee_ids: Optional[List[str]] = None,
    execution_date: Optional[str] = None,
    payment_label: Optional[str] = None,
) -> bytes:
    return _generate_sepa_pain001(
        company_id, period, employee_ids, excluded_employee_ids,
        execution_date, payment_label,
    )


def preview_paiement_organismes(
    company_id: str, period: str, employee_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return _preview_paiement_organismes(company_id, period, employee_ids)


def generate_paiement_organismes_export(
    company_id: str, period: str, employee_ids: Optional[List[str]], file_format: str,
) -> bytes:
    return _generate_paiement_organismes_export(company_id, period, employee_ids, file_format)


def preview_prets_employeur(company_id: str, period: str) -> Dict[str, Any]:
    return _preview_prets_employeur(company_id, period)


def generate_prets_employeur_export(
    company_id: str, period: str, file_format: str,
) -> bytes:
    return _generate_prets_employeur_export(company_id, period, file_format)


def preview_attestations(
    company_id: str, period: str, employee_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return _preview_attestations(company_id, period, employee_ids)


def generate_attestations_export(
    company_id: str, period: str, employee_ids: Optional[List[str]], file_format: str,
) -> bytes:
    return _generate_attestations_export(company_id, period, employee_ids, file_format)

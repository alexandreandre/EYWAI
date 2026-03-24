# app/modules/payroll/exports/formats_cabinet.py
# Migré depuis services/exports/formats_cabinet.py. Exports formats cabinet comptable.

import csv
import io
from typing import Any, Dict, List, Optional

from app.modules.payroll.exports.ecritures_comptables import (
    get_payslip_data_for_od,
    generate_od_salaires,
    generate_od_charges_sociales,
    generate_od_pas,
)
from app.shared.utils.export import format_period, generate_csv, generate_xlsx


def generate_cabinet_generic_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    format: str = "csv"
) -> bytes:
    """Génère un export format cabinet générique"""
    ecritures_salaires, _, _ = generate_od_salaires(company_id, period, employee_ids)
    ecritures_charges, _, _ = generate_od_charges_sociales(company_id, period, employee_ids)
    ecritures_pas, _, _ = generate_od_pas(company_id, period, employee_ids)

    all_ecritures = ecritures_salaires + ecritures_charges + ecritures_pas

    headers = [
        'Date',
        'Journal',
        'Compte',
        'Libellé',
        'Débit',
        'Crédit',
        'Analytique',
        'Référence',
        'Période'
    ]

    data = []
    for ecriture in all_ecritures:
        data.append({
            'Date': ecriture['date_ecriture'],
            'Journal': ecriture['journal'],
            'Compte': ecriture['compte_comptable'],
            'Libellé': ecriture['libelle'],
            'Débit': ecriture['debit'],
            'Crédit': ecriture['credit'],
            'Analytique': ecriture.get('analytique', ''),
            'Référence': ecriture.get('reference_export', ''),
            'Période': ecriture['periode_paie']
        })

    sheet_name = f"Export Cabinet {format_period(period)}"

    if format == "xlsx":
        return generate_xlsx(data, headers, sheet_name)
    else:
        return generate_csv(data, headers)


def generate_cabinet_quadra_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    format: str = "csv"
) -> bytes:
    """Génère un export format Quadra"""
    ecritures_salaires, _, _ = generate_od_salaires(company_id, period, employee_ids)
    ecritures_charges, _, _ = generate_od_charges_sociales(company_id, period, employee_ids)
    ecritures_pas, _, _ = generate_od_pas(company_id, period, employee_ids)

    all_ecritures = ecritures_salaires + ecritures_charges + ecritures_pas

    headers = [
        'Journal',
        'Date',
        'Compte',
        'Libellé',
        'Débit',
        'Crédit',
        'Analytique'
    ]

    data = []
    for ecriture in all_ecritures:
        data.append({
            'Journal': ecriture['journal'],
            'Date': ecriture['date_ecriture'].replace('-', '/'),
            'Compte': ecriture['compte_comptable'],
            'Libellé': ecriture['libelle'],
            'Débit': ecriture['debit'],
            'Crédit': ecriture['credit'],
            'Analytique': ecriture.get('analytique', '')
        })

    sheet_name = f"Quadra {format_period(period)}"

    if format == "xlsx":
        return generate_xlsx(data, headers, sheet_name)
    else:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers, delimiter=';')
        writer.writeheader()
        for row in data:
            writer.writerow(row)
        return output.getvalue().encode('utf-8')


def generate_cabinet_sage_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    format: str = "csv"
) -> bytes:
    """Génère un export format Sage"""
    ecritures_salaires, _, _ = generate_od_salaires(company_id, period, employee_ids)
    ecritures_charges, _, _ = generate_od_charges_sociales(company_id, period, employee_ids)
    ecritures_pas, _, _ = generate_od_pas(company_id, period, employee_ids)

    all_ecritures = ecritures_salaires + ecritures_charges + ecritures_pas

    headers = [
        'Date',
        'Journal',
        'Compte',
        'Libellé',
        'Débit',
        'Crédit',
        'Analytique',
        'Référence'
    ]

    data = []
    for ecriture in all_ecritures:
        data.append({
            'Date': ecriture['date_ecriture'],
            'Journal': ecriture['journal'],
            'Compte': ecriture['compte_comptable'],
            'Libellé': ecriture['libelle'],
            'Débit': ecriture['debit'],
            'Crédit': ecriture['credit'],
            'Analytique': ecriture.get('analytique', ''),
            'Référence': ecriture.get('reference_export', '')
        })

    sheet_name = f"Sage {format_period(period)}"

    if format == "xlsx":
        return generate_xlsx(data, headers, sheet_name)
    else:
        return generate_csv(data, headers)


def preview_cabinet_export(
    company_id: str,
    period: str,
    export_type: str,
    employee_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Prévise un export format cabinet sans générer de fichier"""
    anomalies = []
    warnings = []

    payslip_list, totals = get_payslip_data_for_od(company_id, period, employee_ids)

    if totals['employees_count'] == 0:
        anomalies.append({
            'type': 'error',
            'message': 'Aucun bulletin trouvé pour cette période',
            'severity': 'blocking'
        })

    return {
        'employees_count': totals['employees_count'],
        'totals': totals,
        'anomalies': anomalies,
        'warnings': warnings,
        'can_generate': len([a for a in anomalies if a.get('severity') == 'blocking']) == 0
    }

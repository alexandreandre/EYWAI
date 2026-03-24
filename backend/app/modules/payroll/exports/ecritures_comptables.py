# app/modules/payroll/exports/ecritures_comptables.py
# Migré depuis services/exports/ecritures_comptables.py. Export des écritures comptables (OD).

from calendar import monthrange
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import supabase
from app.shared.utils.export import format_period, generate_csv, generate_xlsx


DEFAULT_MAPPINGS = {
    "salaire_brut": {
        "rubrique_code": "salaire_brut",
        "rubrique_libelle": "Salaire brut",
        "compte_comptable": "641000",
        "sens": "debit",
        "type_rubrique": "salaire",
        "journal": "OD"
    },
    "net_a_payer": {
        "rubrique_code": "net_a_payer",
        "rubrique_libelle": "Net à payer",
        "compte_comptable": "425000",
        "sens": "credit",
        "type_rubrique": "dette_salarie",
        "journal": "OD"
    },
    "cotisation_salariale": {
        "rubrique_code": "cotisation_salariale",
        "rubrique_libelle": "Cotisations salariales",
        "compte_comptable": "425000",
        "sens": "credit",
        "type_rubrique": "dette_salarie",
        "journal": "OD"
    },
    "cotisation_patronale": {
        "rubrique_code": "cotisation_patronale",
        "rubrique_libelle": "Charges sociales patronales",
        "compte_comptable": "645000",
        "sens": "debit",
        "type_rubrique": "charge_patronale",
        "journal": "OD"
    },
    "pas": {
        "rubrique_code": "pas",
        "rubrique_libelle": "Prélèvement à la source",
        "compte_comptable": "425100",
        "sens": "credit",
        "type_rubrique": "pas",
        "journal": "OD"
    }
}


def get_accounting_mappings(company_id: str) -> Dict[str, Dict[str, Any]]:
    """Récupère les mappings comptables pour une entreprise"""
    try:
        response = supabase.table('accounting_mappings').select('*').eq('company_id', company_id).eq('is_active', True).execute()
        mappings = {}
        for mapping in response.data or []:
            mappings[mapping['rubrique_code']] = mapping
        return mappings
    except Exception as e:
        print(f"Erreur lors de la récupération des mappings: {e}")
        return {}


def get_default_mapping(rubrique_code: str) -> Optional[Dict[str, Any]]:
    """Retourne le mapping par défaut pour une rubrique"""
    return DEFAULT_MAPPINGS.get(rubrique_code)


def get_payslip_data_for_od(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    od_type: str = "od_salaires"
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Récupère les données de paie nécessaires pour générer une OD

    Returns:
        tuple: (liste des bulletins avec données, totaux)
    """
    year, month = map(int, period.split("-"))

    query = supabase.table('payslips').select(
        """
        id,
        employee_id,
        month,
        year,
        payslip_data,
        employees!inner(
            id,
            first_name,
            last_name,
            company_id
        )
        """
    ).eq('company_id', company_id).eq('year', year).eq('month', month)

    if employee_ids:
        query = query.in_('employee_id', employee_ids)

    response = query.execute()
    payslips = response.data or []

    totals = {
        'total_brut': 0.0,
        'total_net_a_payer': 0.0,
        'total_cotisations_salariales': 0.0,
        'total_cotisations_patronales': 0.0,
        'total_pas': 0.0,
        'employees_count': 0
    }

    payslip_list = []
    for payslip in payslips:
        employee = payslip.get('employees', {})
        payslip_data = payslip.get('payslip_data', {})

        if not isinstance(payslip_data, dict):
            continue

        brut = float(payslip_data.get('salaire_brut', 0) or 0)
        net_a_payer = float(payslip_data.get('net_a_payer', 0) or 0)

        synthese_net = payslip_data.get('synthese_net', {})
        net_imposable = float(synthese_net.get('net_imposable', 0) if isinstance(synthese_net, dict) else 0)
        pas = float(synthese_net.get('impot_preleve_a_la_source', 0) if isinstance(synthese_net, dict) else 0)

        cotisations = payslip_data.get('structure_cotisations', {})
        cotisations_list = cotisations.get('cotisations', []) if isinstance(cotisations, dict) else []

        cotisations_salariales = 0.0
        cotisations_patronales = 0.0

        for coti in cotisations_list:
            if isinstance(coti, dict):
                cotisations_salariales += float(coti.get('montant_salarial', 0) or 0)
                cotisations_patronales += float(coti.get('montant_patronal', 0) or 0)

        payslip_list.append({
            'payslip_id': payslip['id'],
            'employee_id': employee.get('id'),
            'employee_name': f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip(),
            'brut': brut,
            'net_a_payer': net_a_payer,
            'cotisations_salariales': cotisations_salariales,
            'cotisations_patronales': cotisations_patronales,
            'pas': pas,
            'cotisations_detail': cotisations_list
        })

        totals['total_brut'] += brut
        totals['total_net_a_payer'] += net_a_payer
        totals['total_cotisations_salariales'] += cotisations_salariales
        totals['total_cotisations_patronales'] += cotisations_patronales
        totals['total_pas'] += pas
        totals['employees_count'] += 1

    return payslip_list, totals


def generate_od_salaires(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    date_ecriture: Optional[str] = None,
    regroupement: str = "global"
) -> Tuple[List[Dict[str, Any]], Dict[str, float], Dict[str, Any]]:
    """Génère les écritures comptables pour les salaires"""
    payslip_list, totals = get_payslip_data_for_od(company_id, period, employee_ids, "od_salaires")
    mappings = get_accounting_mappings(company_id)

    if not date_ecriture:
        year, month = map(int, period.split("-"))
        last_day = monthrange(year, month)[1]
        date_ecriture = f"{year}-{month:02d}-{last_day:02d}"

    ecritures = []

    mapping_brut = mappings.get("salaire_brut") or get_default_mapping("salaire_brut")
    if mapping_brut:
        ecritures.append({
            'date_ecriture': date_ecriture,
            'journal': mapping_brut.get('journal', 'OD'),
            'compte_comptable': mapping_brut['compte_comptable'],
            'libelle': f"Salaires {format_period(period)}",
            'debit': totals['total_brut'],
            'credit': 0.0,
            'analytique': mapping_brut.get('analytique'),
            'reference_export': f"OD_SAL_{period}",
            'periode_paie': period
        })

    mapping_net = mappings.get("net_a_payer") or get_default_mapping("net_a_payer")
    if mapping_net:
        ecritures.append({
            'date_ecriture': date_ecriture,
            'journal': mapping_net.get('journal', 'OD'),
            'compte_comptable': mapping_net['compte_comptable'],
            'libelle': f"Net à payer {format_period(period)}",
            'debit': 0.0,
            'credit': totals['total_net_a_payer'],
            'analytique': mapping_net.get('analytique'),
            'reference_export': f"OD_SAL_{period}",
            'periode_paie': period
        })

    mapping_cot_sal = mappings.get("cotisation_salariale") or get_default_mapping("cotisation_salariale")
    if mapping_cot_sal and totals['total_cotisations_salariales'] > 0:
        ecritures.append({
            'date_ecriture': date_ecriture,
            'journal': mapping_cot_sal.get('journal', 'OD'),
            'compte_comptable': mapping_cot_sal['compte_comptable'],
            'libelle': f"Cotisations salariales {format_period(period)}",
            'debit': 0.0,
            'credit': totals['total_cotisations_salariales'],
            'analytique': mapping_cot_sal.get('analytique'),
            'reference_export': f"OD_SAL_{period}",
            'periode_paie': period
        })

    mapping_cot_pat = mappings.get("cotisation_patronale") or get_default_mapping("cotisation_patronale")
    if mapping_cot_pat and totals['total_cotisations_patronales'] > 0:
        ecritures.append({
            'date_ecriture': date_ecriture,
            'journal': mapping_cot_pat.get('journal', 'OD'),
            'compte_comptable': mapping_cot_pat['compte_comptable'],
            'libelle': f"Charges sociales patronales {format_period(period)}",
            'debit': totals['total_cotisations_patronales'],
            'credit': 0.0,
            'analytique': mapping_cot_pat.get('analytique'),
            'reference_export': f"OD_SAL_{period}",
            'periode_paie': period
        })

    mapping_pas = mappings.get("pas") or get_default_mapping("pas")
    if mapping_pas and totals['total_pas'] > 0:
        ecritures.append({
            'date_ecriture': date_ecriture,
            'journal': mapping_pas.get('journal', 'OD'),
            'compte_comptable': mapping_pas['compte_comptable'],
            'libelle': f"Prélèvement à la source {format_period(period)}",
            'debit': 0.0,
            'credit': totals['total_pas'],
            'analytique': mapping_pas.get('analytique'),
            'reference_export': f"OD_SAL_{period}",
            'periode_paie': period
        })

    total_debit = sum(e['debit'] for e in ecritures)
    total_credit = sum(e['credit'] for e in ecritures)

    od_totals = {
        'total_debit': total_debit,
        'total_credit': total_credit,
        'equilibre': abs(total_debit - total_credit) < 0.01,
        'ecart': abs(total_debit - total_credit)
    }

    return ecritures, od_totals, mappings


def generate_od_charges_sociales(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    date_ecriture: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, float], Dict[str, Any]]:
    """Génère les écritures comptables pour les charges sociales par caisse"""
    payslip_list, totals = get_payslip_data_for_od(company_id, period, employee_ids, "od_charges_sociales")
    mappings = get_accounting_mappings(company_id)

    if not date_ecriture:
        year, month = map(int, period.split("-"))
        last_day = monthrange(year, month)[1]
        date_ecriture = f"{year}-{month:02d}-{last_day:02d}"

    ecritures = []
    charges_par_caisse = {}

    for payslip in payslip_list:
        for coti in payslip.get('cotisations_detail', []):
            if not isinstance(coti, dict):
                continue

            libelle_cotisation = coti.get('libelle', 'Cotisation')
            organisme = 'AUTRE'
            if 'URSSAF' in libelle_cotisation.upper():
                organisme = 'URSSAF'
            elif 'RETRAITE' in libelle_cotisation.upper() or 'AGIRC' in libelle_cotisation.upper() or 'ARRCO' in libelle_cotisation.upper():
                organisme = 'RETRAITE'
            elif 'PREVOYANCE' in libelle_cotisation.upper():
                organisme = 'PREVOYANCE'
            elif 'MUTUELLE' in libelle_cotisation.upper():
                organisme = 'MUTUELLE'

            montant_patronal = float(coti.get('montant_patronal', 0) or 0)

            if montant_patronal > 0:
                key = f"{organisme}_{libelle_cotisation}"
                if key not in charges_par_caisse:
                    charges_par_caisse[key] = {
                        'organisme': organisme,
                        'libelle': libelle_cotisation,
                        'montant': 0.0
                    }
                charges_par_caisse[key]['montant'] += montant_patronal

    mapping_cot_pat = mappings.get("cotisation_patronale") or get_default_mapping("cotisation_patronale")

    for key, charge in charges_par_caisse.items():
        if mapping_cot_pat:
            ecritures.append({
                'date_ecriture': date_ecriture,
                'journal': mapping_cot_pat.get('journal', 'OD'),
                'compte_comptable': mapping_cot_pat['compte_comptable'],
                'libelle': f"Charges {charge['libelle']} - {charge['organisme']} {format_period(period)}",
                'debit': charge['montant'],
                'credit': 0.0,
                'analytique': mapping_cot_pat.get('analytique'),
                'reference_export': f"OD_CHG_{period}",
                'periode_paie': period
            })

    mapping_dette = mappings.get("dette_organisme") or {
        "compte_comptable": "431000",
        "journal": "OD"
    }

    total_charges = sum(c['montant'] for c in charges_par_caisse.values())
    if total_charges > 0:
        ecritures.append({
            'date_ecriture': date_ecriture,
            'journal': mapping_dette.get('journal', 'OD'),
            'compte_comptable': mapping_dette['compte_comptable'],
            'libelle': f"Dettes organismes sociaux {format_period(period)}",
            'debit': 0.0,
            'credit': total_charges,
            'analytique': mapping_dette.get('analytique'),
            'reference_export': f"OD_CHG_{period}",
            'periode_paie': period
        })

    total_debit = sum(e['debit'] for e in ecritures)
    total_credit = sum(e['credit'] for e in ecritures)

    od_totals = {
        'total_debit': total_debit,
        'total_credit': total_credit,
        'equilibre': abs(total_debit - total_credit) < 0.01,
        'ecart': abs(total_debit - total_credit)
    }

    return ecritures, od_totals, mappings


def generate_od_pas(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    date_ecriture: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, float], Dict[str, Any]]:
    """Génère les écritures comptables pour le PAS"""
    payslip_list, totals = get_payslip_data_for_od(company_id, period, employee_ids, "od_pas")
    mappings = get_accounting_mappings(company_id)

    if not date_ecriture:
        year, month = map(int, period.split("-"))
        last_day = monthrange(year, month)[1]
        date_ecriture = f"{year}-{month:02d}-{last_day:02d}"

    ecritures = []
    mapping_pas = mappings.get("pas") or get_default_mapping("pas")

    if totals['total_pas'] > 0:
        ecritures.append({
            'date_ecriture': date_ecriture,
            'journal': mapping_pas.get('journal', 'OD'),
            'compte_comptable': mapping_pas['compte_comptable'],
            'libelle': f"PAS {format_period(period)}",
            'debit': totals['total_pas'],
            'credit': 0.0,
            'analytique': mapping_pas.get('analytique'),
            'reference_export': f"OD_PAS_{period}",
            'periode_paie': period
        })

        mapping_dette = mappings.get("net_a_payer") or get_default_mapping("net_a_payer")
        if mapping_dette:
            ecritures.append({
                'date_ecriture': date_ecriture,
                'journal': mapping_dette.get('journal', 'OD'),
                'compte_comptable': mapping_dette['compte_comptable'],
                'libelle': f"PAS déduit du net {format_period(period)}",
                'debit': 0.0,
                'credit': totals['total_pas'],
                'analytique': mapping_dette.get('analytique'),
                'reference_export': f"OD_PAS_{period}",
                'periode_paie': period
            })

    total_debit = sum(e['debit'] for e in ecritures)
    total_credit = sum(e['credit'] for e in ecritures)

    od_totals = {
        'total_debit': total_debit,
        'total_credit': total_credit,
        'equilibre': abs(total_debit - total_credit) < 0.01,
        'ecart': abs(total_debit - total_credit)
    }

    return ecritures, od_totals, mappings


def preview_od(
    company_id: str,
    period: str,
    od_type: str,
    employee_ids: Optional[List[str]] = None,
    date_ecriture: Optional[str] = None
) -> Dict[str, Any]:
    """Prévise une OD sans générer de fichier"""
    anomalies = []
    warnings = []

    if od_type == "od_salaires":
        ecritures, od_totals, mappings = generate_od_salaires(company_id, period, employee_ids, date_ecriture)
    elif od_type == "od_charges_sociales":
        ecritures, od_totals, mappings = generate_od_charges_sociales(company_id, period, employee_ids, date_ecriture)
    elif od_type == "od_pas":
        ecritures, od_totals, mappings = generate_od_pas(company_id, period, employee_ids, date_ecriture)
    else:
        return {
            'anomalies': [{'type': 'error', 'message': f'Type d\'OD non supporté: {od_type}', 'severity': 'blocking'}],
            'can_generate': False
        }

    if not od_totals['equilibre']:
        anomalies.append({
            'type': 'error',
            'message': f"OD non équilibrée: écart de {od_totals['ecart']:.2f}€",
            'severity': 'blocking'
        })

    if len(ecritures) == 0:
        anomalies.append({
            'type': 'error',
            'message': 'Aucune écriture à générer',
            'severity': 'blocking'
        })

    if not mappings:
        warnings.append("Utilisation des mappings par défaut. Configurez vos mappings comptables pour personnaliser.")

    return {
        'nombre_lignes': len(ecritures),
        'total_debit': od_totals['total_debit'],
        'total_credit': od_totals['total_credit'],
        'equilibre': od_totals['equilibre'],
        'ecart': od_totals['ecart'],
        'anomalies': anomalies,
        'warnings': warnings,
        'can_generate': len([a for a in anomalies if a.get('severity') == 'blocking']) == 0,
        'mapping_utilise': mappings
    }


def generate_od_export_file(
    ecritures: List[Dict[str, Any]],
    od_type: str,
    period: str,
    format: str = "csv"
) -> bytes:
    """Génère le fichier d'export OD"""
    headers = [
        'Date écriture',
        'Journal',
        'Compte comptable',
        'Libellé',
        'Débit',
        'Crédit',
        'Analytique',
        'Référence export',
        'Période de paie'
    ]

    data = []
    for ecriture in ecritures:
        data.append({
            'Date écriture': ecriture['date_ecriture'],
            'Journal': ecriture['journal'],
            'Compte comptable': ecriture['compte_comptable'],
            'Libellé': ecriture['libelle'],
            'Débit': ecriture['debit'],
            'Crédit': ecriture['credit'],
            'Analytique': ecriture.get('analytique', ''),
            'Référence export': ecriture.get('reference_export', ''),
            'Période de paie': ecriture['periode_paie']
        })

    type_labels = {
        "od_salaires": "OD Salaires",
        "od_charges_sociales": "OD Charges sociales",
        "od_pas": "OD PAS"
    }

    sheet_name = type_labels.get(od_type, "OD") + f" {format_period(period)}"

    if format == "xlsx":
        return generate_xlsx(data, headers, sheet_name)
    else:
        return generate_csv(data, headers)

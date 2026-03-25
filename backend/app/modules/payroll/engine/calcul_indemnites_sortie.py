"""
Module de calcul des indemnités de sortie selon le droit du travail français

Calcule:
- Indemnité de préavis
- Congés payés restants
- Indemnité de licenciement (Article L1234-9)
- Indemnité de rupture conventionnelle
"""

import sys
from typing import Dict, Any
from datetime import date, datetime
from dateutil.relativedelta import relativedelta


# ============================================================================
# CALCULS DE BASE
# ============================================================================

def calculer_anciennete_annees(hire_date: date, exit_date: date) -> float:
    """
    Calcule l'ancienneté en années (avec décimales)

    Args:
        hire_date: Date d'embauche
        exit_date: Date de sortie

    Returns:
        Ancienneté en années décimales
    """
    delta = relativedelta(exit_date, hire_date)
    years = delta.years
    months = delta.months
    days = delta.days

    # Convertir en années décimales
    anciennete = years + (months / 12) + (days / 365)

    print(f"  Ancienneté: {years} ans, {months} mois, {days} jours = {anciennete:.2f} ans", file=sys.stderr)

    return round(anciennete, 2)


def calculer_salaire_reference_12_mois(employee_data: Dict[str, Any]) -> float:
    """
    Calcule le salaire de référence sur les 12 derniers mois

    Pour une implémentation complète, il faudrait:
    - Récupérer les 12 derniers bulletins de paie
    - Calculer la moyenne du brut
    - Inclure primes annuelles, 13ème mois, etc.

    Pour l'instant, utilise le salaire de base
    """
    salaire_base_obj = employee_data.get('salaire_de_base', {})

    if isinstance(salaire_base_obj, dict):
        salaire_base = salaire_base_obj.get('valeur', 0)
    else:
        salaire_base = salaire_base_obj or 0

    # TODO: Implémenter le calcul réel à partir des bulletins
    return float(salaire_base)


def calculer_salaire_reference_3_mois(employee_data: Dict[str, Any]) -> float:
    """
    Calcule le salaire de référence sur les 3 derniers mois

    Pour une implémentation complète, il faudrait:
    - Récupérer les 3 derniers bulletins de paie
    - Calculer la moyenne du brut

    Pour l'instant, utilise le salaire de base
    """
    salaire_base_obj = employee_data.get('salaire_de_base', {})

    if isinstance(salaire_base_obj, dict):
        salaire_base = salaire_base_obj.get('valeur', 0)
    else:
        salaire_base = salaire_base_obj or 0

    return float(salaire_base)


# ============================================================================
# INDEMNITÉ DE PRÉAVIS
# ============================================================================

def calculer_indemnite_preavis(
    salaire_mensuel_brut: float,
    notice_period_days: int,
    notice_indemnity_type: str
) -> Dict[str, Any]:
    """
    Calcule l'indemnité de préavis

    Formule: (salaire mensuel brut / 30) × nombre de jours de préavis

    Args:
        salaire_mensuel_brut: Salaire mensuel brut de référence
        notice_period_days: Nombre de jours de préavis
        notice_indemnity_type: 'paid', 'waived', 'not_applicable'

    Returns:
        Dict contenant le montant et les détails du calcul
    """
    print("\n  [PRÉAVIS]", file=sys.stderr)
    print(f"    Salaire mensuel: {salaire_mensuel_brut:.2f} €", file=sys.stderr)
    print(f"    Jours de préavis: {notice_period_days}", file=sys.stderr)
    print(f"    Type: {notice_indemnity_type}", file=sys.stderr)

    if notice_indemnity_type != 'paid' or notice_period_days == 0:
        return {
            'montant': 0.0,
            'jours_preavis': notice_period_days,
            'type': notice_indemnity_type,
            'description': 'Indemnité de préavis',
            'calcul': 'Non applicable ou dispensé'
        }

    # Calcul: (salaire mensuel brut / 30) × nombre de jours
    indemnite = (salaire_mensuel_brut / 30) * notice_period_days

    print(f"    Indemnité: ({salaire_mensuel_brut} / 30) × {notice_period_days} = {indemnite:.2f} €", file=sys.stderr)

    return {
        'montant': round(indemnite, 2),
        'jours_preavis': notice_period_days,
        'salaire_reference': salaire_mensuel_brut,
        'type': notice_indemnity_type,
        'description': f'Indemnité compensatrice de préavis ({notice_period_days} jours)',
        'calcul': f'({salaire_mensuel_brut:.2f} / 30) × {notice_period_days} jours = {indemnite:.2f} €'
    }


# ============================================================================
# INDEMNITÉ DE LICENCIEMENT
# ============================================================================

def calculer_indemnite_licenciement(
    anciennete_annees: float,
    salaire_reference: float,
    is_gross_misconduct: bool = False
) -> Dict[str, Any]:
    """
    Calcule l'indemnité légale de licenciement selon le Code du travail français

    Article L1234-9 du Code du travail (2025):
    - Faute grave/lourde: pas d'indemnité
    - < 8 mois d'ancienneté: pas d'indemnité
    - >= 8 mois:
        * 1/4 de mois de salaire par année d'ancienneté (10 premières années)
        * 1/3 de mois de salaire par année au-delà de 10 ans

    Args:
        anciennete_annees: Ancienneté en années
        salaire_reference: Salaire de référence (moyenne 12 ou 3 derniers mois)
        is_gross_misconduct: Faute grave ou lourde

    Returns:
        Dict contenant le montant et les détails du calcul
    """
    print("\n  [LICENCIEMENT]", file=sys.stderr)
    print(f"    Ancienneté: {anciennete_annees:.2f} ans", file=sys.stderr)
    print(f"    Salaire référence: {salaire_reference:.2f} €", file=sys.stderr)
    print(f"    Faute grave: {is_gross_misconduct}", file=sys.stderr)

    if is_gross_misconduct:
        return {
            'montant': 0.0,
            'anciennete': anciennete_annees,
            'description': 'Indemnité de licenciement',
            'calcul': 'Faute grave/lourde - pas d\'indemnité',
            'motif': 'Faute grave/lourde'
        }

    if anciennete_annees < (8/12):  # Moins de 8 mois
        return {
            'montant': 0.0,
            'anciennete': anciennete_annees,
            'description': 'Indemnité de licenciement',
            'calcul': 'Ancienneté insuffisante (< 8 mois)',
            'motif': 'Ancienneté < 8 mois'
        }

    # Calcul pour les 10 premières années: 1/4 de mois par an
    annees_tranche1 = min(anciennete_annees, 10)
    indemnite_tranche1 = (salaire_reference * annees_tranche1) / 4

    print(f"    Tranche 1 (≤10 ans): {annees_tranche1:.2f} ans × 1/4 = {indemnite_tranche1:.2f} €", file=sys.stderr)

    # Calcul au-delà de 10 ans: 1/3 de mois par an
    indemnite_tranche2 = 0.0
    annees_tranche2 = 0.0

    if anciennete_annees > 10:
        annees_tranche2 = anciennete_annees - 10
        indemnite_tranche2 = (salaire_reference * annees_tranche2) / 3
        print(f"    Tranche 2 (>10 ans): {annees_tranche2:.2f} ans × 1/3 = {indemnite_tranche2:.2f} €", file=sys.stderr)

    indemnite_totale = indemnite_tranche1 + indemnite_tranche2

    print(f"    TOTAL: {indemnite_totale:.2f} €", file=sys.stderr)

    return {
        'montant': round(indemnite_totale, 2),
        'anciennete': anciennete_annees,
        'salaire_reference': salaire_reference,
        'tranche1_annees': annees_tranche1,
        'tranche1_montant': round(indemnite_tranche1, 2),
        'tranche2_annees': annees_tranche2,
        'tranche2_montant': round(indemnite_tranche2, 2),
        'description': 'Indemnité légale de licenciement (Article L1234-9)',
        'calcul': f'Tranche 1: {annees_tranche1:.2f} ans × 1/4 mois ({indemnite_tranche1:.2f} €)' +
                  (f' + Tranche 2: {annees_tranche2:.2f} ans × 1/3 mois ({indemnite_tranche2:.2f} €)' if annees_tranche2 > 0 else '')
    }


# ============================================================================
# INDEMNITÉ DE RUPTURE CONVENTIONNELLE
# ============================================================================

def calculer_indemnite_rupture_conventionnelle(
    anciennete_annees: float,
    salaire_reference: float
) -> Dict[str, Any]:
    """
    Calcule l'indemnité de rupture conventionnelle

    Minimum légal = indemnité légale de licenciement
    En pratique, souvent négociée au-dessus du minimum

    Args:
        anciennete_annees: Ancienneté en années
        salaire_reference: Salaire de référence

    Returns:
        Dict contenant le montant minimum et les détails
    """
    print("\n  [RUPTURE CONVENTIONNELLE]", file=sys.stderr)

    # Minimum légal = indemnité de licenciement
    indemnite_licenciement = calculer_indemnite_licenciement(
        anciennete_annees, salaire_reference, is_gross_misconduct=False
    )

    montant_minimum = indemnite_licenciement['montant']

    print(f"    Minimum légal: {montant_minimum:.2f} € (= indemnité licenciement)", file=sys.stderr)
    print(f"    Montant négocié: {montant_minimum:.2f} € (utiliser le minimum par défaut)", file=sys.stderr)

    return {
        'montant_minimum': montant_minimum,
        'montant_negocie': montant_minimum,  # Par défaut, peut être ajusté
        'anciennete': anciennete_annees,
        'salaire_reference': salaire_reference,
        'description': 'Indemnité de rupture conventionnelle',
        'calcul': f'Minimum légal = {montant_minimum:.2f} € (indemnité de licenciement)',
        'details_licenciement': indemnite_licenciement
    }


# ============================================================================
# CONGÉS PAYÉS RESTANTS
# ============================================================================

def calculer_indemnite_conges_restants(
    employee_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    supabase_client=None
) -> Dict[str, Any]:
    """
    Calcule l'indemnité compensatrice de congés payés restants

    Utilise la logique du système de gestion des absences pour calculer:
    - Les congés payés acquis selon la période de référence (1er juin N-1 -> 31 mai N)
    - Les congés payés pris depuis l'embauche
    - Le solde restant
    - L'indemnité selon la méthode la plus avantageuse (1/10ème ou maintien de salaire)
    """
    print("\n  [CONGÉS PAYÉS]", file=sys.stderr)

    salaire_base_obj = employee_data.get('salaire_de_base', {})
    if isinstance(salaire_base_obj, dict):
        salaire_base = salaire_base_obj.get('valeur', 0)
    else:
        salaire_base = salaire_base_obj or 0

    # Récupérer la date d'embauche
    hire_date_str = employee_data.get('hire_date')
    if not hire_date_str:
        print("    ⚠ Date d'embauche non trouvée, calcul simplifié", file=sys.stderr)
        return {
            'montant': 0.0,
            'jours_restants': 0.0,
            'salaire_reference': salaire_base,
            'description': 'Indemnité compensatrice de congés payés',
            'calcul': 'Date d\'embauche non trouvée - calcul impossible',
            'note': 'Date d\'embauche manquante'
        }

    if isinstance(hire_date_str, str):
        hire_date = datetime.fromisoformat(hire_date_str).date()
    else:
        hire_date = hire_date_str

    # Date de sortie
    exit_date_str = exit_data.get('last_working_day')
    if isinstance(exit_date_str, str):
        exit_date = datetime.fromisoformat(exit_date_str).date()
    else:
        exit_date = exit_date_str

    jours_restants = 0.0
    indemnite = 0.0
    cp_acquis = 0.0
    cp_pris = 0.0

    # Si on a accès à supabase, calculer le solde réel
    if supabase_client:
        try:
            import math

            # Calculer les congés acquis selon la logique du système
            # Période de référence: 1er juin N-1 -> 31 mai N
            today = exit_date
            if today.month < 6:
                period_start = date(today.year - 2, 6, 1)
                period_end = date(today.year - 1, 5, 31)
            else:
                period_start = date(today.year - 1, 6, 1)
                period_end = date(today.year, 5, 31)

            # Si embauché après la fin de la période, pas de congés acquis
            if hire_date <= period_end:
                start_of_calculation = max(hire_date, period_start)
                months_worked = (period_end.year - start_of_calculation.year) * 12 + (period_end.month - start_of_calculation.month) + 1
                cp_acquis = math.ceil(months_worked * 2.5)
            else:
                cp_acquis = 0.0

            # Récupérer les congés payés pris
            employee_id = employee_data.get('id')
            cp_pris_resp = supabase_client.table('absence_requests').select("start_date, end_date") \
                .eq('employee_id', employee_id) \
                .eq('type', 'conge_paye') \
                .eq('status', 'validated') \
                .execute()

            cp_pris = 0.0
            if cp_pris_resp.data:
                for req in cp_pris_resp.data:
                    start = datetime.fromisoformat(req['start_date']).date()
                    end = datetime.fromisoformat(req['end_date']).date()
                    cp_pris += (end - start).days + 1

            jours_restants = max(0, cp_acquis - cp_pris)

            print(f"    Congés acquis: {cp_acquis} jours", file=sys.stderr)
            print(f"    Congés pris: {cp_pris} jours", file=sys.stderr)
            print(f"    Solde restant: {jours_restants} jours", file=sys.stderr)

        except Exception as e:
            print(f"    ⚠ Erreur calcul solde congés: {e}, utilisation calcul simplifié", file=sys.stderr)
            cp_acquis = 0.0
            cp_pris = 0.0

    # Calcul de l'indemnité selon la méthode la plus avantageuse
    # 1. Méthode du maintien de salaire: (salaire mensuel / 22) × jours
    indemnite_maintien = jours_restants * (salaire_base / 22)

    # 2. Méthode du 1/10ème: (salaire brut annuel / 10)
    # Pour une année complète, c'est 2.5 jours × 12 = 30 jours
    # Donc 1/10 du salaire annuel correspond à 30 jours
    # Pour X jours: (salaire annuel / 10) × (X / 30) = salaire mensuel × 12 / 10 × X / 30
    indemnite_dixieme = (salaire_base * 12 / 10) * (jours_restants / 30)

    # Prendre la méthode la plus avantageuse pour le salarié
    indemnite = max(indemnite_maintien, indemnite_dixieme)

    print(f"    Indemnité (maintien): {indemnite_maintien:.2f} €", file=sys.stderr)
    print(f"    Indemnité (1/10ème): {indemnite_dixieme:.2f} €", file=sys.stderr)
    print(f"    Indemnité retenue: {indemnite:.2f} € (méthode la plus avantageuse)", file=sys.stderr)

    return {
        'montant': round(indemnite, 2),
        'jours_restants': round(jours_restants, 2),
        'salaire_reference': salaire_base,
        'description': 'Indemnité compensatrice de congés payés',
        'calcul': f'{jours_restants} jours restants × méthode la plus avantageuse = {indemnite:.2f} € (maintien: {indemnite_maintien:.2f} €, 1/10ème: {indemnite_dixieme:.2f} €)',
        'details': {
            'conges_acquis': cp_acquis if supabase_client else None,
            'conges_pris': cp_pris if supabase_client else None,
            'indemnite_maintien': round(indemnite_maintien, 2),
            'indemnite_dixieme': round(indemnite_dixieme, 2),
            'methode_retenue': 'maintien' if indemnite_maintien >= indemnite_dixieme else 'dixieme'
        }
    }


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

def calculer_indemnites_sortie(
    employee_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    supabase_client=None
) -> Dict[str, Any]:
    """
    Fonction principale pour calculer toutes les indemnités de sortie

    Args:
        employee_data: Données de l'employé (id, hire_date, salaire_de_base, etc.)
        exit_data: Données du processus de sortie (exit_type, last_working_day, etc.)

    Returns:
        Dict contenant tous les calculs d'indemnités avec détails
    """
    print("\n" + "="*70, file=sys.stderr)
    print("CALCUL DES INDEMNITÉS DE SORTIE", file=sys.stderr)
    print("="*70, file=sys.stderr)

    # Extraire les données nécessaires
    hire_date_str = employee_data.get('hire_date')
    if not hire_date_str:
        raise ValueError("Date d'embauche (hire_date) non trouvée dans employee_data")

    if isinstance(hire_date_str, str):
        hire_date = datetime.fromisoformat(hire_date_str).date()
    else:
        hire_date = hire_date_str

    exit_date_str = exit_data.get('last_working_day')
    if not exit_date_str:
        raise ValueError("Date de sortie (last_working_day) non trouvée dans exit_data")

    if isinstance(exit_date_str, str):
        exit_date = datetime.fromisoformat(exit_date_str).date()
    else:
        exit_date = exit_date_str

    exit_type = exit_data.get('exit_type')
    notice_period_days = exit_data.get('notice_period_days', 0)
    notice_indemnity_type = exit_data.get('notice_indemnity_type', 'not_applicable')
    is_gross_misconduct = exit_data.get('is_gross_misconduct', False)

    print(f"\nEmployé: {employee_data.get('first_name')} {employee_data.get('last_name')}", file=sys.stderr)
    print(f"Type de sortie: {exit_type}", file=sys.stderr)
    print(f"Date d'embauche: {hire_date}", file=sys.stderr)
    print(f"Date de sortie: {exit_date}", file=sys.stderr)

    # 1. Calculer l'ancienneté
    anciennete = calculer_anciennete_annees(hire_date, exit_date)

    # 2. Déterminer le salaire de référence
    salaire_ref_12 = calculer_salaire_reference_12_mois(employee_data)
    salaire_ref_3 = calculer_salaire_reference_3_mois(employee_data)

    # Prendre le plus avantageux pour le salarié
    salaire_reference = max(salaire_ref_12, salaire_ref_3)

    print(f"\nSalaire référence (12 mois): {salaire_ref_12:.2f} €", file=sys.stderr)
    print(f"Salaire référence (3 mois): {salaire_ref_3:.2f} €", file=sys.stderr)
    print(f"Salaire référence retenu: {salaire_reference:.2f} €", file=sys.stderr)

    # 3. Calculer l'indemnité de préavis
    indemnite_preavis = calculer_indemnite_preavis(
        salaire_reference,
        notice_period_days,
        notice_indemnity_type
    )

    # 4. Calculer les congés payés restants
    indemnite_conges = calculer_indemnite_conges_restants(employee_data, exit_data, supabase_client)

    # 5. Calculer l'indemnité spécifique selon le type de sortie
    indemnite_licenciement = None
    indemnite_rupture = None

    if exit_type == 'licenciement':
        indemnite_licenciement = calculer_indemnite_licenciement(
            anciennete, salaire_reference, is_gross_misconduct
        )

    elif exit_type == 'rupture_conventionnelle':
        indemnite_rupture = calculer_indemnite_rupture_conventionnelle(
            anciennete, salaire_reference
        )

    # 6. Calculer les totaux
    total_brut = (
        indemnite_preavis['montant'] +
        indemnite_conges['montant']
    )

    if indemnite_licenciement:
        total_brut += indemnite_licenciement['montant']

    if indemnite_rupture:
        total_brut += indemnite_rupture.get('montant_negocie', 0)

    # Calcul du net (simplifié - en réalité, certaines indemnités sont exonérées)
    # TODO: Appliquer les règles fiscales et sociales spécifiques
    # - Indemnité de licenciement: exonérée jusqu'à 2× le salaire annuel brut ou 50% de l'indemnité versée
    # - Indemnité de rupture: exonérée jusqu'à 8 000 €
    total_net = total_brut  # Temporaire

    print(f"\n{'='*70}", file=sys.stderr)
    print("RÉSUMÉ DES INDEMNITÉS:", file=sys.stderr)
    print(f"  - Préavis: {indemnite_preavis['montant']:.2f} €", file=sys.stderr)
    print(f"  - Congés payés: {indemnite_conges['montant']:.2f} €", file=sys.stderr)

    if indemnite_licenciement:
        print(f"  - Licenciement: {indemnite_licenciement['montant']:.2f} €", file=sys.stderr)

    if indemnite_rupture:
        print(f"  - Rupture conventionnelle: {indemnite_rupture.get('montant_negocie', 0):.2f} €", file=sys.stderr)

    print(f"\nTOTAL BRUT: {total_brut:.2f} €", file=sys.stderr)
    print(f"TOTAL NET (estimé): {total_net:.2f} €", file=sys.stderr)
    print(f"{'='*70}\n", file=sys.stderr)

    # Construire le résultat
    result = {
        'exit_id': exit_data.get('id'),
        'employee_id': employee_data.get('id'),
        'anciennete_annees': anciennete,
        'salaire_reference': salaire_reference,
        'indemnite_preavis': indemnite_preavis,
        'indemnite_conges': indemnite_conges,
        'total_gross_indemnities': round(total_brut, 2),
        'total_net_indemnities': round(total_net, 2),
        'calculation_date': datetime.now().isoformat(),
        'calculation_details': {
            'hire_date': hire_date.isoformat(),
            'exit_date': exit_date.isoformat(),
            'exit_type': exit_type,
            'is_gross_misconduct': is_gross_misconduct,
            'salaire_ref_12_mois': salaire_ref_12,
            'salaire_ref_3_mois': salaire_ref_3
        }
    }

    # Ajouter les indemnités spécifiques selon le type
    if indemnite_licenciement:
        result['indemnite_licenciement'] = indemnite_licenciement
    else:
        result['indemnite_licenciement'] = {
            'montant': 0.0,
            'description': 'Indemnité de licenciement',
            'calcul': 'Non applicable'
        }

    if indemnite_rupture:
        result['indemnite_rupture_conventionnelle'] = {
            'montant': indemnite_rupture.get('montant_negocie', 0),
            'description': indemnite_rupture.get('description', 'Indemnité de rupture conventionnelle'),
            'calcul': indemnite_rupture.get('calcul', ''),
            'details': indemnite_rupture
        }
    else:
        result['indemnite_rupture_conventionnelle'] = {
            'montant': 0.0,
            'description': 'Indemnité de rupture conventionnelle',
            'calcul': 'Non applicable'
        }

    return result

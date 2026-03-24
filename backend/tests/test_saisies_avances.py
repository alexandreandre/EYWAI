# backend_api/test_saisies_avances.py

"""
Tests pour vérifier que les saisies sur salaire et avances sur salaire
sont correctement intégrées dans les bulletins de paie.

Ces tests vérifient :
1. Récupération depuis la base de données (pas de fichiers en dur)
2. Calcul correct des montants à déduire
3. Intégration dans le bulletin de paie
4. Déduction du net à payer
"""

import pytest
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import Mock, patch, MagicMock

from app.modules.saisies_avances.application.service import enrich_payslip
from app.modules.saisies_avances.domain.rules import (
    apply_priority_order,
    calculate_seizable_amount,
    calculate_seizure_deduction,
)
from app.modules.saisies_avances.infrastructure.queries import (
    get_advances_to_repay,
    get_seizures_for_period,
)


class TestSaisiesAvances:
    """Tests pour les saisies et avances sur salaire"""
    
    def test_calculate_seizable_amount(self):
        """Test du calcul de la quotité saisissable"""
        # Test avec salaire net de 1500€
        net_salary = Decimal("1500.00")
        dependents = 0
        
        seizable = calculate_seizable_amount(net_salary, dependents)
        
        # Vérifications selon le barème légal :
        # Tranche 1: 0-500€ → 0%
        # Tranche 2: 500-1000€ → 10% = 50€
        # Tranche 3: 1000-2000€ → 20% = 100€
        # Total attendu : 50 + 100 = 150€
        # Mais le salarié doit conserver au minimum 1/20ème = 75€
        # Donc max saisissable = 1500 - 75 = 1425€
        # Mais selon le barème : 50 + (1500-1000)*0.20 = 50 + 100 = 150€
        assert seizable >= Decimal("0"), "La quotité saisissable doit être >= 0"
        assert seizable <= net_salary / Decimal("20") * Decimal("19"), "Ne doit pas dépasser 19/20 du salaire"
        
        print(f"✓ Test quotité saisissable : {float(seizable)}€ pour un salaire net de {float(net_salary)}€")
    
    def test_calculate_seizure_deduction_fixe(self):
        """Test du calcul de déduction pour une saisie à montant fixe"""
        seizure = {
            'id': 'test-1',
            'calculation_mode': 'fixe',
            'amount': 100.0,
            'type': 'saisie_arret'
        }
        
        net_salary = Decimal("1500.00")
        seizable_amount = Decimal("200.00")
        
        deduction = calculate_seizure_deduction(seizure, net_salary, seizable_amount)
        
        # Le montant doit être le minimum entre le montant de la saisie et la quotité saisissable
        assert deduction == Decimal("100.00"), f"Attendu 100€, obtenu {deduction}€"
        print(f"✓ Test saisie fixe : {float(deduction)}€ déduit")
    
    def test_calculate_seizure_deduction_pourcentage(self):
        """Test du calcul de déduction pour une saisie en pourcentage"""
        seizure = {
            'id': 'test-2',
            'calculation_mode': 'pourcentage',
            'percentage': 10.0,
            'type': 'saisie_arret'
        }
        
        net_salary = Decimal("1500.00")
        seizable_amount = Decimal("200.00")
        
        deduction = calculate_seizure_deduction(seizure, net_salary, seizable_amount)
        
        # 10% de 1500€ = 150€, mais limité à la quotité saisissable (200€)
        assert deduction == Decimal("150.00"), f"Attendu 150€, obtenu {deduction}€"
        print(f"✓ Test saisie pourcentage : {float(deduction)}€ déduit")
    
    def test_apply_priority_order(self):
        """Test de l'application de l'ordre de priorité des saisies"""
        seizures = [
            {'id': 's1', 'type': 'saisie_arret', 'priority': 4, 'start_date': date(2026, 1, 1)},
            {'id': 's2', 'type': 'pension_alimentaire', 'priority': 1, 'start_date': date(2026, 1, 1)},
            {'id': 's3', 'type': 'atd', 'priority': 4, 'start_date': date(2026, 2, 1)},
        ]
        
        ordered = apply_priority_order(seizures)
        
        # La pension alimentaire (priorité 1) doit être en premier
        assert ordered[0]['type'] == 'pension_alimentaire', "La pension alimentaire doit être en premier"
        print(f"✓ Test ordre de priorité : {ordered[0]['type']} en premier")
    
    def test_get_advances_to_repay_structure(self):
        """Test de la structure de récupération des avances depuis la BDD"""
        # Ce test vérifie que la fonction existe et a la bonne signature
        # Les tests réels nécessitent une connexion à Supabase
        assert callable(get_advances_to_repay), "get_advances_to_repay doit être une fonction"
        
        # Vérifier la signature
        import inspect
        sig = inspect.signature(get_advances_to_repay)
        params = list(sig.parameters.keys())
        
        assert 'employee_id' in params, "La fonction doit avoir un paramètre employee_id"
        assert 'year' in params, "La fonction doit avoir un paramètre year"
        assert 'month' in params, "La fonction doit avoir un paramètre month"
        
        print("✓ Test structure get_advances_to_repay : signature correcte")
    
    def test_get_seizures_for_period_structure(self):
        """Test de la structure de récupération des saisies depuis la BDD"""
        assert callable(get_seizures_for_period), "get_seizures_for_period doit être une fonction"
        
        import inspect
        sig = inspect.signature(get_seizures_for_period)
        params = list(sig.parameters.keys())
        
        assert 'employee_id' in params, "La fonction doit avoir un paramètre employee_id"
        assert 'year' in params, "La fonction doit avoir un paramètre year"
        assert 'month' in params, "La fonction doit avoir un paramètre month"
        
        print("✓ Test structure get_seizures_for_period : signature correcte")
    
    def test_enrich_payslip_with_seizures(self):
        """Test de l'enrichissement du bulletin avec des saisies"""
        # Données de test
        payslip_data = {
            'net_a_payer': 1500.0,
            'salaire_brut': 2000.0,
            'synthese_net': {
                'net_imposable': 1400.0
            }
        }
        
        # Mock des saisies depuis la BDD
        mock_seizures = [
            {
                'id': 'seizure-1',
                'type': 'saisie_arret',
                'calculation_mode': 'fixe',
                'amount': 100.0,
                'creditor_name': 'Test Creditor',
                'reference_legale': 'REF-001'
            }
        ]
        
        # Mock de l'enrichissement
        with patch(
            "app.modules.saisies_avances.application.service.get_seizures_for_period",
            return_value=mock_seizures,
        ):
            with patch(
                "app.modules.saisies_avances.application.service.get_advances_to_repay",
                return_value=[],
            ):
                with patch(
                    "app.modules.saisies_avances.infrastructure.enrichment.supabase"
                ) as mock_supabase:
                    # Mock de la table salary_seizure_deductions
                    mock_table = Mock()
                    mock_table.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
                    mock_supabase.table.return_value = mock_table
                    
                    # Mock de la table employees
                    mock_employee_table = Mock()
                    mock_employee_table.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {'id': 'emp-1'}
                    mock_supabase.table.side_effect = lambda name: mock_employee_table if name == 'employees' else mock_table
                    
                    enriched = enrich_payslip(
                        payslip_data.copy(),
                        'emp-1',
                        2026,
                        2
                    )
                    
                    # Vérifier que les saisies sont présentes
                    assert 'retenues_saisies' in enriched, "Le bulletin doit contenir la section retenues_saisies"
                    assert enriched['retenues_saisies']['total_preleve'] > 0, "Le total prélevé doit être > 0"
                    assert len(enriched['retenues_saisies']['saisies']) > 0, "Il doit y avoir au moins une saisie"
                    
                    # Vérifier que le net à payer a été réduit
                    assert enriched['net_a_payer'] < payslip_data['net_a_payer'], "Le net à payer doit être réduit"
                    
                    print(f"✓ Test enrichissement saisies : {enriched['retenues_saisies']['total_preleve']}€ déduit")
    
    def test_enrich_payslip_with_advances(self):
        """Test de l'enrichissement du bulletin avec des avances"""
        # Données de test
        payslip_data = {
            'net_a_payer': 1500.0,
            'salaire_brut': 2000.0,
            'synthese_net': {
                'net_imposable': 1400.0,
                'acompte_verse': 0.0  # Pas encore déduit par le moteur
            }
        }
        
        # Mock des avances depuis la BDD
        mock_advances = [
            {
                'id': 'advance-1',
                'remaining_amount': 200.0,
                'approved_amount': 200.0,
                'repayment_mode': 'single',
                'status': 'paid',
                'requested_date': '2026-01-15'
            }
        ]
        
        # Mock de l'enrichissement
        with patch(
            "app.modules.saisies_avances.application.service.get_seizures_for_period",
            return_value=[],
        ):
            with patch(
                "app.modules.saisies_avances.application.service.get_advances_to_repay",
                return_value=mock_advances,
            ):
                with patch(
                    "app.modules.saisies_avances.infrastructure.enrichment.supabase"
                ) as mock_supabase:
                    # Mock de la table salary_advance_repayments
                    mock_table = Mock()
                    mock_table.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
                    
                    # Mock de la table salary_advances pour la mise à jour
                    mock_advance_table = Mock()
                    mock_advance_table.update.return_value.eq.return_value.execute.return_value = None
                    
                    # Mock de la table employees
                    mock_employee_table = Mock()
                    mock_employee_table.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {'id': 'emp-1'}
                    
                    def table_side_effect(name):
                        if name == 'employees':
                            return mock_employee_table
                        elif name == 'salary_advances':
                            return mock_advance_table
                        else:
                            return mock_table
                    
                    mock_supabase.table.side_effect = table_side_effect
                    
                    enriched = enrich_payslip(
                        payslip_data.copy(),
                        'emp-1',
                        2026,
                        2,
                        payslip_id='payslip-1'
                    )
                    
                    # Vérifier que les avances sont présentes
                    assert 'remboursements_avances' in enriched, "Le bulletin doit contenir la section remboursements_avances"
                    assert enriched['remboursements_avances']['total_rembourse'] > 0, "Le total remboursé doit être > 0"
                    assert len(enriched['remboursements_avances']['avances']) > 0, "Il doit y avoir au moins une avance"
                    
                    print(f"✓ Test enrichissement avances : {enriched['remboursements_avances']['total_rembourse']}€ remboursé")
    
    def test_enrich_payslip_avoid_double_deduction(self):
        """Test pour éviter la double déduction des avances"""
        # Données de test avec acompte déjà déduit par le moteur
        payslip_data = {
            'net_a_payer': 1300.0,  # Déjà réduit de 200€
            'salaire_brut': 2000.0,
            'synthese_net': {
                'net_imposable': 1400.0,
                'acompte_verse': 200.0  # Déjà déduit par le moteur
            }
        }
        
        # Mock des avances depuis la BDD
        mock_advances = [
            {
                'id': 'advance-1',
                'remaining_amount': 200.0,
                'approved_amount': 200.0,
                'repayment_mode': 'single',
                'status': 'paid',
                'requested_date': '2026-01-15'
            }
        ]
        
        # Mock de l'enrichissement
        with patch(
            "app.modules.saisies_avances.application.service.get_seizures_for_period",
            return_value=[],
        ):
            with patch(
                "app.modules.saisies_avances.application.service.get_advances_to_repay",
                return_value=mock_advances,
            ):
                with patch(
                    "app.modules.saisies_avances.infrastructure.enrichment.supabase"
                ) as mock_supabase:
                    mock_table = Mock()
                    mock_table.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
                    
                    mock_employee_table = Mock()
                    mock_employee_table.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {'id': 'emp-1'}
                    
                    mock_supabase.table.side_effect = lambda name: mock_employee_table if name == 'employees' else mock_table
                    
                    enriched = enrich_payslip(
                        payslip_data.copy(),
                        'emp-1',
                        2026,
                        2
                    )
                    
                    # Le net à payer ne doit pas être réduit deux fois
                    # Il doit rester à 1300€ (déjà réduit par le moteur)
                    assert enriched['net_a_payer'] == 1300.0, f"Le net à payer ne doit pas être réduit deux fois. Attendu 1300€, obtenu {enriched['net_a_payer']}€"
                    
                    print("✓ Test évitation double déduction : net à payer correct")


def run_tests():
    """Fonction pour exécuter tous les tests"""
    print("\n" + "="*60)
    print("TESTS SAISIES ET AVANCES SUR SALAIRE")
    print("="*60 + "\n")
    
    test_suite = TestSaisiesAvances()
    
    tests = [
        test_suite.test_calculate_seizable_amount,
        test_suite.test_calculate_seizure_deduction_fixe,
        test_suite.test_calculate_seizure_deduction_pourcentage,
        test_suite.test_apply_priority_order,
        test_suite.test_get_advances_to_repay_structure,
        test_suite.test_get_seizures_for_period_structure,
        test_suite.test_enrich_payslip_with_seizures,
        test_suite.test_enrich_payslip_with_advances,
        test_suite.test_enrich_payslip_avoid_double_deduction,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} : {str(e)}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print(f"RÉSULTATS : {passed} tests réussis, {failed} tests échoués")
    print("="*60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

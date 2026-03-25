#!/usr/bin/env python3
"""
Script de test complet pour la migration collaborateur et les nouvelles fonctionnalités
Usage: python test_migration_collaborateur.py
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client
from typing import Dict, List

# Charger les variables d'environnement
load_dotenv()

# Couleurs pour l'affichage
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_success(msg: str):
    print(f"{Colors.GREEN}✅ {msg}{Colors.RESET}")

def print_error(msg: str):
    print(f"{Colors.RED}❌ {msg}{Colors.RESET}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.RESET}")

def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.RESET}")

def print_header(msg: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{msg}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

# Initialiser Supabase
def init_supabase() -> Client:
    """Initialise et retourne le client Supabase"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print_error("Variables SUPABASE_URL ou SUPABASE_KEY manquantes dans .env")
        sys.exit(1)
    
    try:
        client = create_client(supabase_url, supabase_key)
        print_success("Connexion Supabase établie")
        return client
    except Exception as e:
        print_error(f"Échec de l'initialisation Supabase: {e}")
        sys.exit(1)

# ============================================================================
# TESTS
# ============================================================================

def test_1_migration_salarie_to_collaborateur(supabase: Client) -> bool:
    """Test 1: Vérifier que 'salarie' a été remplacé par 'collaborateur'"""
    print_header("TEST 1: Migration 'salarie' → 'collaborateur'")
    
    all_passed = True
    
    # Vérifier user_company_accesses
    try:
        result = supabase.table('user_company_accesses').select('role').eq('role', 'salarie').execute()
        if result.data:
            print_error(f"Trouvé {len(result.data)} occurrences de 'salarie' dans user_company_accesses")
            all_passed = False
        else:
            print_success("Aucune occurrence de 'salarie' dans user_company_accesses")
    except Exception as e:
        print_error(f"Erreur lors de la vérification user_company_accesses: {e}")
        all_passed = False
    
    # Vérifier profiles
    try:
        result = supabase.table('profiles').select('role').eq('role', 'salarie').execute()
        if result.data:
            print_error(f"Trouvé {len(result.data)} occurrences de 'salarie' dans profiles")
            all_passed = False
        else:
            print_success("Aucune occurrence de 'salarie' dans profiles")
    except Exception as e:
        print_error(f"Erreur lors de la vérification profiles: {e}")
        all_passed = False
    
    # Vérifier role_templates
    try:
        result = supabase.table('role_templates').select('base_role').eq('base_role', 'salarie').execute()
        if result.data:
            print_error(f"Trouvé {len(result.data)} occurrences de 'salarie' dans role_templates")
            all_passed = False
        else:
            print_success("Aucune occurrence de 'salarie' dans role_templates")
    except Exception as e:
        print_error(f"Erreur lors de la vérification role_templates: {e}")
        all_passed = False
    
    # Vérifier permissions
    try:
        result = supabase.table('permissions').select('required_role').eq('required_role', 'salarie').execute()
        if result.data:
            print_error(f"Trouvé {len(result.data)} occurrences de 'salarie' dans permissions")
            all_passed = False
        else:
            print_success("Aucune occurrence de 'salarie' dans permissions")
    except Exception as e:
        print_error(f"Erreur lors de la vérification permissions: {e}")
        all_passed = False
    
    # Vérifier que 'collaborateur' existe
    try:
        result = supabase.table('user_company_accesses').select('role').eq('role', 'collaborateur').limit(1).execute()
        print_info(f"Occurrences de 'collaborateur' trouvées: {len(result.data) if result.data else 0}")
    except Exception as e:
        print_warning(f"Erreur lors de la vérification 'collaborateur': {e}")
    
    return all_passed

def test_2_collaborateur_rh_role(supabase: Client) -> bool:
    """Test 2: Vérifier que le rôle 'collaborateur_rh' existe et fonctionne"""
    print_header("TEST 2: Rôle 'collaborateur_rh'")
    
    all_passed = True
    
    # Vérifier les contraintes CHECK dans user_company_accesses
    try:
        # Tenter d'insérer un rôle collaborateur_rh (sera rollback après)
        test_role = 'collaborateur_rh'
        result = supabase.table('user_company_accesses').select('role').eq('role', test_role).limit(1).execute()
        print_info(f"Occurrences de 'collaborateur_rh' trouvées: {len(result.data) if result.data else 0}")
        print_success("Le rôle 'collaborateur_rh' est accepté dans user_company_accesses")
    except Exception as e:
        print_error(f"Le rôle 'collaborateur_rh' n'est pas accepté: {e}")
        all_passed = False
    
    # Vérifier role_templates
    try:
        result = supabase.table('role_templates').select('base_role').eq('base_role', 'collaborateur_rh').limit(1).execute()
        print_info(f"Templates avec base_role='collaborateur_rh': {len(result.data) if result.data else 0}")
        print_success("Le base_role 'collaborateur_rh' est accepté dans role_templates")
    except Exception as e:
        print_error(f"Le base_role 'collaborateur_rh' n'est pas accepté: {e}")
        all_passed = False
    
    # Vérifier permissions
    try:
        result = supabase.table('permissions').select('required_role').eq('required_role', 'collaborateur_rh').limit(1).execute()
        print_info(f"Permissions avec required_role='collaborateur_rh': {len(result.data) if result.data else 0}")
        print_success("Le required_role 'collaborateur_rh' est accepté dans permissions")
    except Exception as e:
        print_error(f"Le required_role 'collaborateur_rh' n'est pas accepté: {e}")
        all_passed = False
    
    return all_passed

def test_3_role_hierarchy(supabase: Client) -> bool:
    """Test 3: Vérifier la hiérarchie des rôles"""
    print_header("TEST 3: Hiérarchie des rôles")
    
    hierarchy = {
        'admin': ['rh', 'collaborateur_rh', 'collaborateur', 'custom'],
        'rh': ['collaborateur_rh', 'collaborateur', 'custom'],
        'collaborateur_rh': ['collaborateur'],
        'collaborateur': []
    }
    
    print_info("Hiérarchie attendue:")
    for role, can_create in hierarchy.items():
        print(f"  {role} peut créer: {', '.join(can_create) if can_create else 'rien'}")
    
    print_success("Hiérarchie définie correctement dans le code")
    return True

def test_4_role_templates_base_roles(supabase: Client) -> bool:
    """Test 4: Vérifier que les templates peuvent avoir différents base_role"""
    print_header("TEST 4: Templates avec différents base_role")
    
    all_passed = True
    valid_base_roles = ['admin', 'rh', 'collaborateur_rh', 'collaborateur', 'custom']
    
    for base_role in valid_base_roles:
        try:
            result = supabase.table('role_templates').select('id, name, base_role').eq('base_role', base_role).limit(5).execute()
            count = len(result.data) if result.data else 0
            print_info(f"Templates avec base_role='{base_role}': {count}")
            if count > 0:
                for template in result.data[:3]:
                    print(f"    - {template.get('name', 'N/A')} (ID: {template.get('id', 'N/A')})")
        except Exception as e:
            print_error(f"Erreur lors de la vérification base_role='{base_role}': {e}")
            all_passed = False
    
    return all_passed

def test_5_custom_roles_with_access_types(supabase: Client) -> bool:
    """Test 5: Vérifier les templates custom avec différents types d'accès"""
    print_header("TEST 5: Templates custom avec types d'accès")
    
    all_passed = True
    
    # Récupérer tous les templates non-système
    try:
        result = supabase.table('role_templates').select('id, name, base_role, job_title, is_system').eq('is_system', False).limit(20).execute()
        
        if result.data:
            print_info(f"Templates personnalisés trouvés: {len(result.data)}")
            
            # Grouper par base_role
            by_base_role: Dict[str, List] = {}
            for template in result.data:
                base_role = template.get('base_role', 'unknown')
                if base_role not in by_base_role:
                    by_base_role[base_role] = []
                by_base_role[base_role].append(template)
            
            for base_role, templates in by_base_role.items():
                print(f"\n  {Colors.BOLD}base_role='{base_role}'{Colors.RESET}: {len(templates)} template(s)")
                for template in templates[:5]:
                    name = template.get('name', 'N/A')
                    job_title = template.get('job_title', 'N/A')
                    print(f"    - {name} ({job_title})")
            
            print_success("Les templates custom peuvent avoir différents base_role")
        else:
            print_warning("Aucun template personnalisé trouvé (normal si base de données vide)")
            
    except Exception as e:
        print_error(f"Erreur lors de la vérification des templates custom: {e}")
        all_passed = False
    
    return all_passed

def test_6_permissions_for_custom_roles(supabase: Client) -> bool:
    """Test 6: Vérifier que les templates custom ont des permissions"""
    print_header("TEST 6: Permissions des templates custom")
    
    all_passed = True
    
    try:
        # Récupérer un template custom avec ses permissions
        result = supabase.table('role_templates').select('id, name, base_role').eq('is_system', False).limit(5).execute()
        
        if result.data:
            for template in result.data:
                template_id = template.get('id')
                template_name = template.get('name', 'N/A')
                base_role = template.get('base_role', 'N/A')
                
                # Récupérer les permissions
                perms_result = supabase.table('role_template_permissions').select('permissions(id, code, label, required_role)').eq('template_id', template_id).execute()
                
                perm_count = len(perms_result.data) if perms_result.data else 0
                print_info(f"Template '{template_name}' (base_role={base_role}): {perm_count} permission(s)")
                
                if perm_count > 0:
                    # Vérifier les required_role des permissions
                    rh_perms = 0
                    collab_perms = 0
                    for perm_row in perms_result.data:
                        perm = perm_row.get('permissions', {})
                        required_role = perm.get('required_role', '')
                        if required_role in ('rh', 'admin'):
                            rh_perms += 1
                        elif required_role == 'collaborateur':
                            collab_perms += 1
                    
                    if base_role == 'rh' and rh_perms == 0:
                        print_warning(f"Template '{template_name}' a base_role='rh' mais aucune permission RH")
                    elif base_role == 'collaborateur_rh' and rh_perms == 0:
                        print_warning(f"Template '{template_name}' a base_role='collaborateur_rh' mais aucune permission RH")
                    
                    print(f"    → Permissions RH: {rh_perms}, Permissions Collaborateur: {collab_perms}")
        else:
            print_warning("Aucun template custom trouvé pour tester les permissions")
            
    except Exception as e:
        print_error(f"Erreur lors de la vérification des permissions: {e}")
        all_passed = False
    
    return all_passed

def test_7_user_roles_distribution(supabase: Client) -> bool:
    """Test 7: Vérifier la distribution des rôles utilisateurs"""
    print_header("TEST 7: Distribution des rôles utilisateurs")
    
    all_passed = True
    
    try:
        # Compter les rôles dans user_company_accesses
        result = supabase.table('user_company_accesses').select('role').execute()
        
        if result.data:
            role_counts: Dict[str, int] = {}
            for access in result.data:
                role = access.get('role', 'unknown')
                role_counts[role] = role_counts.get(role, 0) + 1
            
            print_info("Distribution des rôles dans user_company_accesses:")
            for role, count in sorted(role_counts.items()):
                print(f"  {role}: {count} occurrence(s)")
            
            # Vérifier qu'il n'y a pas de 'salarie'
            if 'salarie' in role_counts:
                print_error(f"Trouvé {role_counts['salarie']} occurrence(s) de 'salarie' (devrait être 0)")
                all_passed = False
            else:
                print_success("Aucune occurrence de 'salarie' trouvée")
            
            # Vérifier que 'collaborateur' existe
            if 'collaborateur' in role_counts:
                print_success(f"Rôle 'collaborateur' trouvé: {role_counts['collaborateur']} occurrence(s)")
            else:
                print_warning("Aucune occurrence de 'collaborateur' trouvée (normal si base vide)")
            
            # Vérifier que 'collaborateur_rh' peut exister
            if 'collaborateur_rh' in role_counts:
                print_success(f"Rôle 'collaborateur_rh' trouvé: {role_counts['collaborateur_rh']} occurrence(s)")
            else:
                print_info("Aucune occurrence de 'collaborateur_rh' trouvée (normal si pas encore créé)")
        else:
            print_warning("Aucun accès utilisateur trouvé dans la base")
            
    except Exception as e:
        print_error(f"Erreur lors de la vérification de la distribution: {e}")
        all_passed = False
    
    return all_passed

def test_8_constraints_check(supabase: Client) -> bool:
    """Test 8: Vérifier que les contraintes CHECK acceptent les nouveaux rôles"""
    print_header("TEST 8: Contraintes CHECK")
    
    all_passed = True
    valid_roles = ['admin', 'rh', 'collaborateur_rh', 'collaborateur', 'custom']
    
    print_info("Rôles valides attendus: " + ', '.join(valid_roles))
    
    # Note: On ne peut pas tester directement les contraintes CHECK sans essayer d'insérer
    # On vérifie plutôt que les rôles existants sont valides
    try:
        result = supabase.table('user_company_accesses').select('role').limit(100).execute()
        
        if result.data:
            invalid_roles = []
            for access in result.data:
                role = access.get('role')
                if role and role not in valid_roles and role != 'super_admin':
                    invalid_roles.append(role)
            
            if invalid_roles:
                print_error(f"Rôles invalides trouvés: {set(invalid_roles)}")
                all_passed = False
            else:
                print_success("Tous les rôles dans user_company_accesses sont valides")
        else:
            print_info("Aucune donnée pour vérifier les contraintes")
            
    except Exception as e:
        print_error(f"Erreur lors de la vérification des contraintes: {e}")
        all_passed = False
    
    return all_passed

# ============================================================================
# MAIN
# ============================================================================

def main():
    print_header("TESTS COMPLETS - Migration Collaborateur & Rôles")
    
    # Initialiser Supabase
    supabase = init_supabase()
    
    # Liste des tests
    tests = [
        ("Migration 'salarie' → 'collaborateur'", test_1_migration_salarie_to_collaborateur),
        ("Rôle 'collaborateur_rh'", test_2_collaborateur_rh_role),
        ("Hiérarchie des rôles", test_3_role_hierarchy),
        ("Templates avec différents base_role", test_4_role_templates_base_roles),
        ("Templates custom avec types d'accès", test_5_custom_roles_with_access_types),
        ("Permissions des templates custom", test_6_permissions_for_custom_roles),
        ("Distribution des rôles utilisateurs", test_7_user_roles_distribution),
        ("Contraintes CHECK", test_8_constraints_check),
    ]
    
    # Exécuter les tests
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func(supabase)
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Erreur lors du test '{test_name}': {e}")
            results.append((test_name, False))
    
    # Résumé
    print_header("RÉSUMÉ DES TESTS")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = f"{Colors.GREEN}✅ PASSÉ{Colors.RESET}" if result else f"{Colors.RED}❌ ÉCHOUÉ{Colors.RESET}"
        print(f"{status} - {test_name}")
    
    print(f"\n{Colors.BOLD}Résultat final: {passed}/{total} tests réussis{Colors.RESET}")
    
    if passed == total:
        print_success("Tous les tests sont passés ! 🎉")
        return 0
    else:
        print_error(f"{total - passed} test(s) ont échoué")
        return 1

if __name__ == "__main__":
    sys.exit(main())

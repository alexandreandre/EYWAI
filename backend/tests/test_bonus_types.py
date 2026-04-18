#!/usr/bin/env python3
"""
Script de test pour la fonctionnalité Primes (Bonus Types)
Teste les endpoints backend et vérifie l'intégration complète
"""

import os
import sys
from datetime import datetime

from pydantic import ValidationError

from app.core.database import supabase


def print_header(text):
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_test(name, passed=True):
    status = "✅" if passed else "❌"
    print(f"{status} {name}")


def _resolve_test_company_id() -> str | None:
    """Même logique que la fixture test_company_id (conftest) : FK valide pour les inserts."""
    cid = os.getenv("TEST_COMPANY_ID")
    if cid:
        return cid
    try:
        r = supabase.table("companies").select("id").limit(1).execute()
        if r.data:
            return r.data[0].get("id")
    except Exception:
        pass
    return None


def _scenario_table_exists() -> bool:
    """Scénario 1: Vérifier que la table company_bonus_types existe."""
    print_header("TEST 1: Vérification de la table company_bonus_types")
    try:
        supabase.table("company_bonus_types").select("id").limit(1).execute()
        print_test("Table company_bonus_types existe", True)
        return True
    except Exception as e:
        print_test(f"Table company_bonus_types existe: {e}", False)
        return False


def test_table_exists() -> None:
    assert _scenario_table_exists()


def _scenario_table_structure() -> bool:
    """Scénario 2: Vérifier la structure de la table."""
    print_header("TEST 2: Structure de la table")

    try:
        # Essayer de récupérer une ligne vide pour voir la structure
        supabase.table("company_bonus_types").select("*").limit(0).execute()
        print_test("Structure de la table accessible", True)

        company_id = _resolve_test_company_id()
        if not company_id:
            print_test(
                "Insertion de structure: aucune entreprise en base (skip insert), "
                "select * suffit pour valider l'accès",
                True,
            )
            return True

        # Vérifier les colonnes en essayant d'insérer une ligne de test (qu'on supprimera)
        test_data = {
            "company_id": company_id,
            "libelle": "TEST_PRIME_DELETE",
            "type": "montant_fixe",
            "montant": 0.01,
            "soumise_a_cotisations": True,
            "soumise_a_impot": True,
        }

        insert_result = (
            supabase.table("company_bonus_types").insert(test_data).execute()
        )
        if insert_result.data:
            test_id = insert_result.data[0]["id"]
            # Supprimer la ligne de test
            supabase.table("company_bonus_types").delete().eq("id", test_id).execute()
            print_test("Insertion et suppression de test réussies", True)
            return True
        else:
            print_test("Insertion de test échouée", False)
            return False

    except Exception as e:
        print_test(f"Structure de la table: {e}", False)
        return False


def test_table_structure() -> None:
    assert _scenario_table_structure()


def _scenario_monthly_inputs_integration() -> bool:
    """Scénario 3: Vérifier que monthly_inputs peut recevoir des primes."""
    print_header("TEST 3: Intégration avec monthly_inputs")
    try:
        # Vérifier qu'on peut lire depuis monthly_inputs
        result = (
            supabase.table("monthly_inputs")
            .select("id, name, amount, is_socially_taxed, is_taxable")
            .limit(5)
            .execute()
        )
        print_test("Table monthly_inputs accessible", True)

        if result.data:
            print(f"   Exemple de saisie existante: {result.data[0]}")

        return True
    except Exception as e:
        print_test(f"Intégration monthly_inputs: {e}", False)
        return False


def test_monthly_inputs_integration() -> None:
    assert _scenario_monthly_inputs_integration()


def _scenario_payslip_generator_integration() -> bool:
    """Scénario 4: le générateur de bulletin peut lire les monthly_inputs."""
    print_header("TEST 4: Intégration avec le générateur de bulletin")
    try:
        # Vérifier qu'on peut lire les monthly_inputs comme le fait payslip_generator.py
        # (ligne 68 du fichier)
        test_employee_id = "00000000-0000-0000-0000-000000000001"
        test_year = datetime.now().year
        test_month = datetime.now().month

        result = (
            supabase.table("monthly_inputs")
            .select("*")
            .match(
                {
                    "employee_id": test_employee_id,
                    "year": test_year,
                    "month": test_month,
                }
            )
            .execute()
        )

        print_test("Requête monthly_inputs pour bulletin fonctionne", True)
        print(f"   Format: {type(result.data)}")
        return True
    except Exception as e:
        print_test(f"Intégration générateur bulletin: {e}", False)
        return False


def test_payslip_generator_integration() -> None:
    assert _scenario_payslip_generator_integration()


def _scenario_schema_validation() -> bool:
    """Scénario 5: schémas Pydantic corrects."""
    print_header("TEST 5: Validation des schémas Pydantic")
    try:
        from app.modules.bonus_types.schemas import BonusTypeCreate, BonusTypeEnum

        # Test création prime montant_fixe
        BonusTypeCreate(
            libelle="Test Prime Fixe",
            type=BonusTypeEnum.MONTANT_FIXE,
            montant=100.0,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
        )
        print_test("Schéma BonusTypeCreate (montant_fixe) valide", True)

        # Test création prime selon_heures
        BonusTypeCreate(
            libelle="Test Prime Heures",
            type=BonusTypeEnum.SELON_HEURES,
            montant=50.0,
            seuil_heures=150.0,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
        )
        print_test("Schéma BonusTypeCreate (selon_heures) valide", True)

        # Test validation: seuil_heures requis pour selon_heures
        try:
            BonusTypeCreate(
                libelle="Test Prime Invalide",
                type=BonusTypeEnum.SELON_HEURES,
                montant=50.0,
                # seuil_heures manquant - devrait échouer
                soumise_a_cotisations=True,
                soumise_a_impot=True,
            )
            print_test("Validation seuil_heures requis: ÉCHEC (devrait échouer)", False)
            return False
        except (ValueError, ValidationError):
            print_test("Validation seuil_heures requis: OK (échoue comme prévu)", True)

        return True
    except Exception as e:
        print_test(f"Validation schémas: {e}", False)
        import traceback

        traceback.print_exc()
        return False


def test_schema_validation() -> None:
    assert _scenario_schema_validation()


def _scenario_routes_registered() -> bool:
    """Scénario 6: routes bien enregistrées."""
    print_header("TEST 6: Vérification des routes API")
    try:
        from app.main import app

        routes = [route.path for route in app.routes]
        required_routes = [
            "/api/bonus-types",
            "/api/bonus-types/calculate/{bonus_type_id}",
        ]

        all_found = True
        for route in required_routes:
            # Vérifier que la route existe (peut être avec ou sans paramètres)
            found = any(route.split("{")[0] in r for r in routes)
            if found:
                print_test(f"Route {route} enregistrée", True)
            else:
                print_test(f"Route {route} enregistrée", False)
                all_found = False

        return all_found
    except Exception as e:
        print_test(f"Vérification routes: {e}", False)
        import traceback

        traceback.print_exc()
        return False


def test_routes_registered() -> None:
    assert _scenario_routes_registered()


def main():
    """Exécute tous les tests"""
    print("\n" + "=" * 80)
    print("  🧪 TESTS DE LA FONCTIONNALITÉ PRIMES (BONUS TYPES)")
    print("=" * 80)

    tests = [
        ("Table existe", _scenario_table_exists),
        ("Structure table", _scenario_table_structure),
        ("Intégration monthly_inputs", _scenario_monthly_inputs_integration),
        ("Intégration générateur bulletin", _scenario_payslip_generator_integration),
        ("Validation schémas", _scenario_schema_validation),
        ("Routes API", _scenario_routes_registered),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Exception lors du test '{name}': {e}")
            import traceback

            traceback.print_exc()
            results.append((name, False))

    print_header("RÉSULTATS FINAUX")
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")

    print(f"\n📊 Score: {passed}/{total} tests réussis")

    if passed == total:
        print("\n🎉 Tous les tests sont passés ! La fonctionnalité est prête.")
        print("\n📝 Prochaines étapes pour tester manuellement:")
        print("   1. Ouvrir le frontend: http://localhost:5173/saisies")
        print("   2. Cliquer sur 'Nouvelle saisie'")
        print("   3. Tester la création d'une prime dans le catalogue")
        print("   4. Vérifier qu'elle apparaît dans le dropdown")
        print("   5. Créer une saisie mensuelle avec cette prime")
        print("   6. Générer un bulletin et vérifier que la prime apparaît")
    else:
        print(
            f"\n⚠️  {total - passed} test(s) ont échoué. Vérifiez les erreurs ci-dessus."
        )

    print("=" * 80 + "\n")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

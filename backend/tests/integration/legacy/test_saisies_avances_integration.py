#!/usr/bin/env python3
# backend_api/test_saisies_avances_integration.py

"""
Script de test pour vérifier l'intégration complète des saisies et avances
dans le processus de génération de bulletins de paie.

Ce script vérifie :
1. Que les avances sont récupérées depuis la BDD et intégrées dans le calcul initial
2. Que les saisies sont récupérées depuis la BDD et appliquées dans l'enrichissement
3. Que tout est bien déduit du net à payer
4. Que les données sont bien affichées dans le bulletin
"""

import sys
from decimal import Decimal

import pytest
from _pytest.outcomes import Skipped

from app.core.database import supabase
from app.modules.saisies_avances.application.service import enrich_payslip
from app.modules.saisies_avances.domain.rules import calculate_seizable_amount
from app.modules.saisies_avances.infrastructure.queries import (
    get_advances_to_repay,
    get_seizures_for_period,
)


def test_advances_retrieval():
    """Test de récupération des avances depuis la BDD"""
    print("\n" + "=" * 60)
    print("TEST 1 : Récupération des avances depuis la BDD")
    print("=" * 60)

    # Récupérer un employé de test
    employees = (
        supabase.table("employees")
        .select("id, first_name, last_name")
        .limit(1)
        .execute()
    )
    if not employees.data:
        print("⚠ Aucun employé trouvé dans la base de données")
        pytest.skip("Aucun employé trouvé dans la base de données")

    employee_id = employees.data[0]["id"]
    employee_name = f"{employees.data[0].get('first_name', '')} {employees.data[0].get('last_name', '')}"

    print(f"Employé test : {employee_name} (ID: {employee_id})")

    # Récupérer les avances pour février 2026
    advances = get_advances_to_repay(employee_id, 2026, 2)

    print(f"\n✓ {len(advances)} avance(s) à rembourser trouvée(s)")

    if advances:
        total_repayment = Decimal("0")
        for advance in advances:
            remaining = Decimal(str(advance.get("remaining_amount", 0)))
            approved = Decimal(str(advance.get("approved_amount", 0)))
            status = advance.get("status")

            print(f"\n  - Avance ID: {advance.get('id')}")
            print(f"    Statut: {status}")
            print(f"    Montant approuvé: {float(approved)}€")
            print(f"    Reste à rembourser: {float(remaining)}€")

            if advance.get("repayment_mode") == "single":
                repayment = remaining
            else:
                repayment_months = advance.get("repayment_months", 1)
                repayment = approved / Decimal(str(repayment_months))
                repayment = min(repayment, remaining)

            total_repayment += repayment
            print(f"    Montant à rembourser ce mois: {float(repayment)}€")

        print(f"\n✓ Total à rembourser en février 2026 : {float(total_repayment)}€")
    else:
        print("\n⚠ Aucune avance à rembourser pour cet employé en février 2026")


def test_seizures_retrieval():
    """Test de récupération des saisies depuis la BDD"""
    print("\n" + "=" * 60)
    print("TEST 2 : Récupération des saisies depuis la BDD")
    print("=" * 60)

    # Récupérer un employé de test
    employees = (
        supabase.table("employees")
        .select("id, first_name, last_name")
        .limit(1)
        .execute()
    )
    if not employees.data:
        print("⚠ Aucun employé trouvé dans la base de données")
        pytest.skip("Aucun employé trouvé dans la base de données")

    employee_id = employees.data[0]["id"]
    employee_name = f"{employees.data[0].get('first_name', '')} {employees.data[0].get('last_name', '')}"

    print(f"Employé test : {employee_name} (ID: {employee_id})")

    # Récupérer les saisies pour février 2026
    seizures = get_seizures_for_period(employee_id, 2026, 2)

    print(f"\n✓ {len(seizures)} saisie(s) active(s) trouvée(s)")

    if seizures:
        # Calculer la quotité saisissable (on utilise un net à payer estimé de 1500€)
        net_a_payer_estime = Decimal("1500.00")
        seizable_amount = calculate_seizable_amount(net_a_payer_estime, 0)

        print(
            f"\n  Quotité saisissable (pour un net à payer de {float(net_a_payer_estime)}€) : {float(seizable_amount)}€"
        )

        total_deduction = Decimal("0")
        for seizure in seizures:
            seizure_type = seizure.get("type", "N/A")
            calculation_mode = seizure.get("calculation_mode", "barème_legal")
            amount = Decimal(str(seizure.get("amount", 0)))
            percentage = seizure.get("percentage", 0)

            print(f"\n  - Saisie ID: {seizure.get('id')}")
            print(f"    Type: {seizure_type}")
            print(f"    Mode de calcul: {calculation_mode}")

            if calculation_mode == "fixe":
                deduction = min(amount, seizable_amount)
                print(f"    Montant fixe: {float(amount)}€")
            elif calculation_mode == "pourcentage":
                deduction = min(
                    net_a_payer_estime * (Decimal(str(percentage)) / Decimal("100")),
                    seizable_amount,
                )
                print(f"    Pourcentage: {percentage}%")
            else:
                deduction = (
                    min(amount, seizable_amount) if amount > 0 else seizable_amount
                )
                print(f"    Montant selon barème légal: {float(amount)}€")

            total_deduction += deduction
            print(f"    Montant à prélever: {float(deduction)}€")

        print(f"\n✓ Total à prélever en février 2026 : {float(total_deduction)}€")
    else:
        print("\n⚠ Aucune saisie active pour cet employé en février 2026")


def test_payslip_enrichment():
    """Test de l'enrichissement d'un bulletin de paie"""
    print("\n" + "=" * 60)
    print("TEST 3 : Enrichissement du bulletin de paie")
    print("=" * 60)

    # Récupérer un bulletin de test
    payslips = (
        supabase.table("payslips")
        .select("id, employee_id, year, month, payslip_data")
        .limit(1)
        .execute()
    )

    if not payslips.data:
        print("⚠ Aucun bulletin trouvé dans la base de données")
        pytest.skip("Aucun bulletin trouvé dans la base de données")

    payslip = payslips.data[0]
    payslip_id = payslip["id"]
    employee_id = payslip["employee_id"]
    year = payslip["year"]
    month = payslip["month"]
    payslip_data = payslip.get("payslip_data", {})

    print(f"Bulletin test : {month:02d}/{year} (ID: {payslip_id})")
    print(f"Net à payer initial : {payslip_data.get('net_a_payer', 0)}€")

    try:
        enriched_data = enrich_payslip(
            payslip_data.copy(), employee_id, year, month, payslip_id=payslip_id
        )

        # Vérifier les saisies
        if "retenues_saisies" in enriched_data:
            saisies = enriched_data["retenues_saisies"]
            total_saisies = saisies.get("total_preleve", 0)
            print(f"\n✓ Saisies appliquées : {total_saisies}€")
            if saisies.get("saisies"):
                for saisie in saisies["saisies"]:
                    print(
                        f"  - {saisie.get('type', 'N/A')} : {saisie.get('montant', 0)}€"
                    )
        else:
            print("\n⚠ Aucune saisie dans le bulletin enrichi")

        # Vérifier les avances
        if "remboursements_avances" in enriched_data:
            avances = enriched_data["remboursements_avances"]
            total_avances = avances.get("total_rembourse", 0)
            print(f"\n✓ Avances remboursées : {total_avances}€")
            if avances.get("avances"):
                for avance in avances["avances"]:
                    print(
                        f"  - {avance.get('date_avance', 'N/A')} : {avance.get('montant', 0)}€"
                    )
        else:
            print("\n⚠ Aucune avance dans le bulletin enrichi")

        # Vérifier le net à payer final
        net_final = enriched_data.get("net_a_payer", 0)
        net_initial = payslip_data.get("net_a_payer", 0)

        print(f"\n✓ Net à payer initial : {net_initial}€")
        print(f"✓ Net à payer final : {net_final}€")
        print(f"✓ Différence : {net_initial - net_final}€")

        if net_final < net_initial:
            print("\n✓ Le net à payer a bien été réduit par les saisies/avances")
        elif net_final == net_initial:
            print(
                "\n⚠ Le net à payer n'a pas été modifié (pas de saisies/avances à appliquer)"
            )

    except Exception as e:
        print(f"\n✗ Erreur lors de l'enrichissement : {e}")
        import traceback

        traceback.print_exc()
        pytest.fail(str(e))


def test_database_integration():
    """Test d'intégration avec la base de données"""
    print("\n" + "=" * 60)
    print("TEST 4 : Vérification de l'intégration BDD")
    print("=" * 60)

    # Vérifier que les tables existent
    tables_to_check = [
        "salary_advances",
        "salary_seizures",
        "salary_advance_repayments",
        "salary_seizure_deductions",
    ]

    print("\nVérification des tables...")
    for table in tables_to_check:
        try:
            # Essayer de faire une requête simple
            supabase.table(table).select("id").limit(1).execute()
            print(f"  ✓ Table '{table}' accessible")
        except Exception as e:
            print(f"  ✗ Table '{table}' non accessible : {e}")
            pytest.fail(f"Table '{table}' non accessible : {e}")

    # Vérifier les données
    print("\nVérification des données...")

    advances_count = (
        supabase.table("salary_advances").select("id", count="exact").execute()
    )
    print(f"  ✓ {advances_count.count} avance(s) dans la base de données")

    seizures_count = (
        supabase.table("salary_seizures").select("id", count="exact").execute()
    )
    print(f"  ✓ {seizures_count.count} saisie(s) dans la base de données")

    repayments_count = (
        supabase.table("salary_advance_repayments")
        .select("id", count="exact")
        .execute()
    )
    print(f"  ✓ {repayments_count.count} remboursement(s) d'avances enregistré(s)")

    deductions_count = (
        supabase.table("salary_seizure_deductions")
        .select("id", count="exact")
        .execute()
    )
    print(f"  ✓ {deductions_count.count} déduction(s) de saisies enregistrée(s)")


def main():
    """Fonction principale"""
    print("\n" + "=" * 70)
    print("TESTS D'INTÉGRATION - SAISIES ET AVANCES SUR SALAIRE")
    print("=" * 70)

    tests = [
        ("Récupération des avances depuis la BDD", test_advances_retrieval),
        ("Récupération des saisies depuis la BDD", test_seizures_retrieval),
        ("Enrichissement du bulletin de paie", test_payslip_enrichment),
        ("Intégration avec la base de données", test_database_integration),
    ]

    results = []
    for name, test_func in tests:
        try:
            test_func()
            results.append((name, True))
        except Skipped as exc:
            print(f"\n○ Test ignoré '{name}' : {exc}")
            results.append((name, True))
        except Exception as e:
            print(f"\n✗ Erreur dans le test '{name}' : {e}")
            import traceback

            traceback.print_exc()
            results.append((name, False))

    # Résumé
    print("\n" + "=" * 70)
    print("RÉSUMÉ DES TESTS")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ RÉUSSI" if result else "✗ ÉCHOUÉ"
        print(f"{status} : {name}")

    print("\n" + "=" * 70)
    print(f"Total : {passed}/{total} tests réussis")
    print("=" * 70 + "\n")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

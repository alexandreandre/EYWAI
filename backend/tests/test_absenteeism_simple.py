#!/usr/bin/env python3
# Test simple du calcul du taux d'absentéisme

from datetime import date, timedelta

print("=== Test Logique Calcul Taux d'Absentéisme ===\n")

# Simuler les données
num_employees = 1  # Exemple: 1 employé
absence_days_in_period = 3  # Exemple: 3 jours d'absence

# Calculer les jours ouvrés sur 30 jours
today = date.today()
thirty_days_ago = today - timedelta(days=30)

total_working_days = 0
current_date = thirty_days_ago
while current_date <= today:
    if current_date.weekday() < 5:  # Lundi à Vendredi
        total_working_days += 1
    current_date += timedelta(days=1)

print(f"Période: {thirty_days_ago} -> {today}")
print(f"Jours ouvrés dans la période: {total_working_days}")
print(f"Nombre d'employés: {num_employees}")
print(f"Total jours ouvrés théoriques: {total_working_days * num_employees}")
print(f"Jours d'absence: {absence_days_in_period}")
print()

# Calculer le taux
theoretical_working_days = total_working_days * num_employees
if theoretical_working_days > 0:
    absenteeism_rate = (absence_days_in_period / theoretical_working_days) * 100
    print(f"Taux d'absentéisme: {absenteeism_rate:.1f}%")
    print()
    print(f"Formule: ({absence_days_in_period} / {theoretical_working_days}) * 100 = {absenteeism_rate:.1f}%")
else:
    print("Impossible de calculer le taux")

print("\n=== Exemples ===")
print("- Si 0 jours d'absence: 0.0%")
print(f"- Si {total_working_days // 10} jours d'absence (~10%): {((total_working_days // 10) / theoretical_working_days) * 100:.1f}%")
print(f"- Si {total_working_days // 5} jours d'absence (~20%): {((total_working_days // 5) / theoretical_working_days) * 100:.1f}%")

#!/usr/bin/env python3
# Test du calcul du taux d'absentéisme

from datetime import date, timedelta

from app.core.database import supabase

print("=== Test Calcul Taux d'Absentéisme ===\n")

# 1. Récupérer tous les employés
print("1. Récupération des employés...")
employees_resp = (
    supabase.table("employees").select("id, first_name, last_name").execute()
)
employees = employees_resp.data or []
employee_ids = [emp["id"] for emp in employees]
print(f"   ✓ {len(employees)} employés trouvés\n")

# 2. Calculer les jours ouvrés sur 30 jours
today = date.today()
thirty_days_ago = today - timedelta(days=30)

total_working_days = 0
current_date = thirty_days_ago
while current_date <= today:
    if current_date.weekday() < 5:  # Lundi à Vendredi
        total_working_days += 1
    current_date += timedelta(days=1)

print(f"2. Période: {thirty_days_ago} -> {today}")
print(f"   Jours ouvrés théoriques: {total_working_days}")
print(
    f"   Total jours ouvrés (pour {len(employees)} employés): {total_working_days * len(employees)}\n"
)

# 3. Récupérer les absences validées
print("3. Récupération des absences validées...")
absences_resp = (
    supabase.table("absence_requests")
    .select("employee_id, type, selected_days, status")
    .eq("status", "validated")
    .execute()
)

absences = absences_resp.data or []
print(f"   ✓ {len(absences)} absences validées trouvées\n")

# 4. Compter les jours d'absence dans la période
total_absence_days = 0
absence_by_employee = {}

for absence in absences:
    emp_id = absence.get("employee_id")
    if emp_id not in employee_ids:
        continue

    selected_days = absence.get("selected_days", [])
    absence_type = absence.get("type", "inconnu")

    for day_str in selected_days:
        try:
            absence_date = date.fromisoformat(day_str)
            # Vérifier si la date est dans la période et un jour ouvré
            if thirty_days_ago <= absence_date <= today and absence_date.weekday() < 5:
                total_absence_days += 1

                # Compter par employé
                emp = next((e for e in employees if e["id"] == emp_id), None)
                emp_name = f"{emp['first_name']} {emp['last_name']}" if emp else emp_id

                if emp_name not in absence_by_employee:
                    absence_by_employee[emp_name] = {"count": 0, "types": set()}
                absence_by_employee[emp_name]["count"] += 1
                absence_by_employee[emp_name]["types"].add(absence_type)
        except (ValueError, TypeError):
            continue

print("4. Jours d'absence sur la période:")
print(f"   Total jours d'absence: {total_absence_days}")
if absence_by_employee:
    print("\n   Détails par employé:")
    for emp_name, data in sorted(absence_by_employee.items()):
        types = ", ".join(data["types"])
        print(f"   - {emp_name}: {data['count']} jour(s) ({types})")
else:
    print("   Aucune absence dans cette période")
print()

# 5. Calculer le taux
theoretical_working_days = total_working_days * len(employees)
if theoretical_working_days > 0:
    absenteeism_rate = (total_absence_days / theoretical_working_days) * 100
    print("5. Calcul du taux:")
    print(f"   Formule: ({total_absence_days} / {theoretical_working_days}) * 100")
    print(f"   Taux d'absentéisme: {absenteeism_rate:.1f}%")
else:
    print("5. Impossible de calculer le taux (pas de jours ouvrés)")

print("\n=== Test terminé ===")

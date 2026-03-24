"""
Constantes et repères pour les requêtes expenses (table, colonnes, ordre).

Utilisées par le repository ; pas de logique FastAPI.
Comportement identique à l'ancien router (noms de table et de colonnes).
"""
# Table Supabase
TABLE_EXPENSE_REPORTS = "expense_reports"

# Sélection liste RH (avec join employé)
SELECT_ALL_WITH_EMPLOYEE = "*, employee:employees(id, first_name, last_name)"

# Tri par défaut
ORDER_BY_DATE_DESC = "date"
ORDER_BY_CREATED_AT_DESC = "created_at"

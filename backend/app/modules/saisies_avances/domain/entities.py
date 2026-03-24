"""
Entités du domaine saisies et avances.

Placeholder : les modèles métier sont aujourd'hui portés par les schémas Pydantic
et les dict retournés par Supabase. Lors de la migration, on pourra introduire
des entités explicites (SalarySeizure, SalaryAdvance, SalaryAdvancePayment)
sans changer le contrat API.
"""
# Entités cibles (noms pour préparation migration) :
# - SalarySeizure (saisie sur salaire)
# - SalaryAdvance (demande d'avance)
# - SalaryAdvancePayment (versement avec preuve)
# - SalarySeizureDeduction (historique prélèvement)
# - SalaryAdvanceRepayment (historique remboursement)

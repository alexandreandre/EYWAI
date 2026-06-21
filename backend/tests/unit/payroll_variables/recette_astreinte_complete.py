"""
Recette barème astreinte complet — configuration de référence (groupe).

Parcours RH :
1. Appliquer preset « astreinte équipes » (API preset)
2. Renseigner jours pont (PayrollSpecialDaysCard)
3. Types de poste : night_windows rate 0.5 (B_P4)
4. Planning astreintes + fiches km salariés
5. Simuler puis générer variables (mode auto après validation)
6. Générer bulletins
"""

from __future__ import annotations

RECETTE_AMOUNTS = {
    "amount_normal": 176.18,
    "amount_christmas": 352.36,
    "amount_bridge": 250.0,
}

RECETTE_EXPORT_CODES = {
    "BPAS": "Prime d'astreinte",
    "B_S0": "Majoration astreinte samedi",
    "B_VP": "Majoration astreinte dimanche",
    "B_P4": "Heures de nuit (planning postes, pas règle variable)",
}

RECETTE_RULE_CODES = (
    "astreinte_week",
    "astreinte_sat",
    "astreinte_sun",
    "astreinte_km",
)

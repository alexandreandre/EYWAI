"""
DTOs et constantes applicatives du module dashboard.

Constantes partagées pour l'agrégation (libellés de mois, mapping types absence).
"""

from typing import Dict

# Noms de mois en français abrégés pour le graphique (comportement legacy)
MONTH_NAMES_FR: Dict[int, str] = {
    1: "Jan",
    2: "Fév",
    3: "Mar",
    4: "Avr",
    5: "Mai",
    6: "Jui",
    7: "Jui",
    8: "Aoû",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Déc",
}

# Mapping type d'absence -> libellé affiché (team pulse)
ABSENCE_TYPE_LABELS: Dict[str, str] = {
    "conge_paye": "Congé Payé",
    "rtt": "RTT",
    "sans_solde": "Sans Solde",
}

"""
Règles métier pures du domaine monthly_inputs.

Aucune dépendance FastAPI, DB ou infrastructure. Utilisables par l'application si besoin.
Comportement actuel des routeurs inchangé (validation Pydantic côté API).
"""


def is_valid_period(year: int, month: int) -> bool:
    """Période (année, mois) valide pour une saisie mensuelle. Règle pure, sans I/O."""
    return (
        isinstance(year, int)
        and isinstance(month, int)
        and 1 <= month <= 12
        and year > 0
    )


#: Début de la description des saisies écrites par la génération automatique
#: des variables (`payroll_variables.application.generate_monthly`).
PREFIXE_SAISIE_GENEREE = "Auto:"

#: Ce que devient une saisie générée qu'on retire : supprimée, la génération
#: suivante la recréerait ; à 0 et protégée, elle n'y revient pas.
RETRAIT_SAISIE_GENEREE = {"amount": 0, "manual_override": True}


def est_saisie_generee(saisie: dict) -> bool:
    """Saisie écrite par une règle automatique de la société."""
    return str(saisie.get("description") or "").startswith(PREFIXE_SAISIE_GENEREE)


def est_saisie_retiree(saisie: dict) -> bool:
    """Saisie générée que la RH a retirée (à 0, protégée) : pas une ligne du bulletin."""
    return (
        est_saisie_generee(saisie)
        and bool(saisie.get("manual_override"))
        and float(saisie.get("amount") or 0) == 0
    )

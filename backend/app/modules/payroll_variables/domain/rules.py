"""Règles calcul variables paie — domaine pur."""

from __future__ import annotations

from typing import Any, Literal

from app.shared.domain.employment_rules import est_au_forfait_jours, is_cadre

RuleType = Literal[
    "fixed_monthly",
    "per_astreinte_week",
    "per_shift_type",
    "per_worked_day",
    "per_modulation_payout",
    "per_night_hour",
    "per_astreinte_weekend_km",
    "per_astreinte_week_tiered",
    "per_astreinte_weekend_majoration",
    "per_week_without_absence",
    "transport_domicile_travail",
]


def compute_rule_amount(
    rule_type: str,
    amount: float | None,
    rate: float | None,
    quantity: float,
    *,
    conditions: dict[str, Any] | None = None,
) -> float:
    conditions = conditions or {}
    if rule_type == "fixed_monthly":
        return round(float(amount or 0), 2)
    if rule_type == "per_astreinte_week":
        return round(float(amount or 0) * quantity, 2)
    if rule_type in ("per_shift_type", "per_worked_day"):
        return round(float(amount or 0) * quantity, 2)
    if rule_type == "per_night_hour":
        unit = float(rate if rate is not None else amount or 0)
        return round(unit * quantity, 2)
    if rule_type == "per_modulation_payout":
        min_balance = float(conditions.get("min_balance_hours") or 0)
        if quantity < min_balance:
            return 0.0
        return round(float(amount or 0) * quantity, 2)
    if rule_type == "per_week_without_absence":
        per_week = float(conditions.get("amount_per_week") or amount or 0)
        return round(per_week * quantity, 2)
    return 0.0


def _est_alternant(employee: dict[str, Any]) -> bool:
    """Contrat d'apprentissage ou de professionnalisation."""
    contrat = str(employee.get("contract_type") or "").lower()
    return "apprentissage" in contrat or "professionnalisation" in contrat or "alternan" in contrat


def employee_matches_conditions(
    employee: dict[str, Any],
    conditions: dict[str, Any] | None,
) -> bool:
    if not conditions:
        return True
    employee_ids = conditions.get("employee_ids")
    if isinstance(employee_ids, list):
        # Liste vide = règle ciblée mais sans destinataire : ne cible personne.
        cibles = {str(x) for x in employee_ids}
        if str(employee.get("id") or "") not in cibles:
            return False
    statuts = conditions.get("statuts")
    if statuts and isinstance(statuts, list):
        emp_statut = (employee.get("statut") or "").lower()
        if not any(s.lower() in emp_statut for s in statuts):
            return False
    exclude_statuts = conditions.get("exclude_statuts")
    if exclude_statuts and isinstance(exclude_statuts, list):
        emp_statut = (employee.get("statut") or "").lower()
        if any(s.lower() in emp_statut for s in exclude_statuts):
            return False
    # Périmètre des primes de pointage (17/11 : « que la population qui
    # pointe, hors forfait jours, cadres et alternants »). La fiche doit être
    # lue avec `is_forfait_jour` et `contract_type`.
    if conditions.get("exclure_forfait_jours") and est_au_forfait_jours(employee):
        return False
    if conditions.get("exclure_cadres") and is_cadre(employee.get("statut")):
        return False
    if conditions.get("exclure_alternants") and _est_alternant(employee):
        return False
    min_productivity = conditions.get("min_productivity_amount")
    if min_productivity is not None:
        pass
    return True


#: Conditions propres à chaque type de règle. Toute autre clé (salariés visés,
#: situation du repas, code d'export, prime du catalogue, statuts) vaut pour
#: tous les types et reste.
CONDITIONS_PROPRES: dict[str, frozenset[str]] = {
    "per_astreinte_weekend_km": frozenset(
        {
            "km_free_threshold_one_way",
            "round_trip_multiplier",
            "requires_astreinte",
            "requires_weekend_work",
            "astreinte_link_mode",
            "quantity_mode",
            "rate_mode",
            "vehicle_type_default",
            "manual_trips_input_name",
            "weekend_weekday_numbers",
        }
    ),
    "per_astreinte_week_tiered": frozenset(
        {
            "amount_normal",
            "amount_christmas",
            "amount_bridge",
            "christmas_mode",
            "bridge_mode",
            "christmas_detection",
            "bridge_requires_astreinte_on_day",
        }
    ),
    "per_astreinte_weekend_majoration": frozenset(
        {
            "weekday_rates",
            "min_hours",
            "flat_hours",
            "requires_astreinte_same_iso_week",
            "weekend_weekday_numbers",
        }
    ),
    "per_week_without_absence": frozenset(
        {
            "absence_types",
            "amount_per_week",
            "min_locked_shifts_per_week",
            "workflow_steps",
            "periode_assiduite",
            "types_qui_font_perdre",
            "proratiser_temps_partiel",
        }
    ),
    "per_shift_type": frozenset({"shift_type_codes"}),
    "per_worked_day": frozenset({"min_heures", "plages_debut", "heures_par_jour"}),
    "per_night_hour": frozenset({"nuit_de", "nuit_a", "majoration_pct", "depuis_les_pointages"}),
    "per_modulation_payout": frozenset({"min_balance_hours"}),
}


def conditions_du_type(rule_type: str, conditions: dict[str, Any] | None) -> dict[str, Any]:
    """Les conditions qu'une règle de ce type peut porter (Lyon, 17/11/2026 :
    une « indemnité transport » en montant fixe gardait des conditions
    d'astreinte d'un type choisi puis abandonné). Les clés propres aux autres
    types sont retirées ; le choix des salariés est toujours gardé."""
    propres = CONDITIONS_PROPRES.get(rule_type, frozenset())
    d_autres_types = frozenset().union(*CONDITIONS_PROPRES.values()) - propres
    return {k: v for k, v in (conditions or {}).items() if k not in d_autres_types}

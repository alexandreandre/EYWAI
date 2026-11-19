/**
 * Les conditions qu'une règle de variable de paie peut porter, selon son type.
 * Même liste que le serveur (`payroll_variables/domain/rules.py`,
 * CONDITIONS_PROPRES) : les clés propres aux autres types sont retirées, le
 * choix des salariés et les autres clés communes restent (Lyon, 17/11/2026).
 */
const CONDITIONS_PROPRES: Record<string, readonly string[]> = {
  per_astreinte_weekend_km: [
    'km_free_threshold_one_way',
    'round_trip_multiplier',
    'requires_astreinte',
    'requires_weekend_work',
    'astreinte_link_mode',
    'quantity_mode',
    'rate_mode',
    'vehicle_type_default',
    'manual_trips_input_name',
    'weekend_weekday_numbers',
  ],
  per_astreinte_week_tiered: [
    'amount_normal',
    'amount_christmas',
    'amount_bridge',
    'christmas_mode',
    'bridge_mode',
    'christmas_detection',
    'bridge_requires_astreinte_on_day',
  ],
  per_astreinte_weekend_majoration: [
    'weekday_rates',
    'min_hours',
    'flat_hours',
    'requires_astreinte_same_iso_week',
    'weekend_weekday_numbers',
  ],
  per_week_without_absence: [
    'absence_types',
    'amount_per_week',
    'min_locked_shifts_per_week',
    'workflow_steps',
    'periode_assiduite',
    'types_qui_font_perdre',
    'proratiser_temps_partiel',
  ],
  per_shift_type: ['shift_type_codes'],
  per_worked_day: ['min_heures', 'plages_debut', 'heures_par_jour'],
  per_night_hour: ['nuit_de', 'nuit_a', 'majoration_pct'],
  per_modulation_payout: ['min_balance_hours'],
};

export function conditionsDuType(
  ruleType: string | undefined,
  conditions: Record<string, unknown> | null | undefined,
): Record<string, unknown> {
  const propres = new Set(CONDITIONS_PROPRES[ruleType ?? ''] ?? []);
  const dAutresTypes = new Set(
    Object.values(CONDITIONS_PROPRES)
      .flat()
      .filter((k) => !propres.has(k)),
  );
  return Object.fromEntries(Object.entries(conditions ?? {}).filter(([k]) => !dAutresTypes.has(k)));
}

/** Un panier se paie par repas : en montant fixe mensuel, le moteur n'y voit
 * qu'un seul panier (15 € → 7,50 € exonérés, 7,50 € réintégrés). */
export function panierEnMontantFixe(label: string | undefined, ruleType: string | undefined): boolean {
  return ruleType === 'fixed_monthly' && /panier|repas/i.test(label ?? '');
}

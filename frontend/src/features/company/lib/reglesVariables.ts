// Types de règles des Variables de paie, et l'indemnité de trajet de la fiche.

export const RULE_TYPE_LABELS: Record<string, string> = {
  fixed_monthly: 'Montant fixe mensuel',
  per_astreinte_week: 'Par semaine d\'astreinte (simple)',
  per_astreinte_week_tiered: 'Astreinte hebdo (Noël / pont)',
  per_astreinte_weekend_majoration: 'Majoration astreinte WE',
  per_shift_type: 'Par type de poste',
  per_modulation_payout: 'Prime liquidation modulation',
  per_night_hour: 'Par heure de nuit',
  per_astreinte_weekend_km: 'Indemnité km astreinte',
  per_week_without_absence: 'Par semaine sans absence',
  // Le moteur ne verse l'indemnité de la fiche que par cette règle : sans elle
  // dans la liste, impossible de la créer à l'écran ([B6], 12/10/2026).
  transport_domicile_travail: 'Indemnité de trajet domicile-travail',
};

/** Règles dont le montant ne se saisit pas sur la règle (calculé, ou lu sur chaque fiche). */
export const REGLES_SANS_MONTANT = new Set<string>([
  'per_astreinte_weekend_km',
  'per_astreinte_week_tiered',
  'per_astreinte_weekend_majoration',
  'transport_domicile_travail',
]);

export const LIBELLE_INDEMNITE_TRAJET = 'Indemnité de trajet domicile-travail (€ net/mois)';

/** Même texte à la création et sur la fiche : la création disait « versé en net chaque mois », faux sans la règle. */
export const AIDE_INDEMNITE_TRAJET =
  'Montant prévu à l’avenant. Versé seulement si la règle « Indemnité de trajet domicile-travail » existe dans Variables de paie : elle le propose chaque mois dans Saisies > Primes, proratisé à l’entrée et à la sortie, retiré en cas d’absence sur tout le mois.';

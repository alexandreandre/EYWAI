// Situation du repas d'un panier : elle fixe le plafond d'exonération Urssaf
// (barème frais_pro). Non précisée, le moteur prend le plafond le plus haut.
export type SituationRepas = 'sur_lieu_travail' | 'hors_locaux_sans_restaurant' | 'hors_locaux_avec_restaurant';

export const SITUATIONS_REPAS: { valeur: SituationRepas; libelle: string }[] = [
  { valeur: 'sur_lieu_travail', libelle: 'Sur le lieu de travail (équipe, poste, nuit) : 7,50 €' },
  { valeur: 'hors_locaux_sans_restaurant', libelle: 'En déplacement, sans restaurant : 10,40 €' },
  { valeur: 'hors_locaux_avec_restaurant', libelle: 'En déplacement, au restaurant : 21,40 €' },
];

/** Les paniers d'atelier sont pris sur le lieu de travail (c'est aussi le plafond de Quadra). */
export const SITUATION_REPAS_PAR_DEFAUT: SituationRepas = 'sur_lieu_travail';

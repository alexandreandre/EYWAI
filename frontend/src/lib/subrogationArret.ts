/** Case « subrogation » d'un arrêt (retour d'Elsa du 16/11). */
export type ChoixSubrogation = 'societe' | 'oui' | 'non';

/** Le choix par défaut dit ce que la règle de la société fera. */
export function phraseSubrogationDeLaSociete(mode: string | null | undefined): string {
  switch (mode) {
    case 'never':
      return 'Règle de la société : pas de subrogation';
    case 'at_mp_only':
      return 'Règle de la société : oui pour un accident du travail ou une maladie professionnelle, avec droit au maintien';
    case undefined:
    case null:
      return 'Règle de la société';
    default:
      return 'Règle de la société : oui quand le salarié a droit au maintien';
  }
}

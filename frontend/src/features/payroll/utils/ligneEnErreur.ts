/**
 * Ligne d'un bulletin non généré. Un refus d'une garde de la paie (jour à
 * saisir, jour « absent » sans type…) n'est pas une panne : « Réessayer » en
 * rouge laissait croire qu'un nouvel essai suffirait. Le refus se dit
 * « Refusé », avec un bouton neutre ; le message de la ligne dit quoi faire.
 */
export interface PresentationLigneEnErreur {
  badge: 'Refusé' | 'Échec';
  bouton: 'Générer' | 'Réessayer';
  boutonRouge: boolean;
}

export function presentationLigneEnErreur(refus: boolean | undefined): PresentationLigneEnErreur {
  return refus
    ? { badge: 'Refusé', bouton: 'Générer', boutonRouge: false }
    : { badge: 'Échec', bouton: 'Réessayer', boutonRouge: true };
}

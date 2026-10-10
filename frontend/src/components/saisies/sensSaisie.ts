/**
 * Où va le montant d'une saisie du mois : sur le brut (prime) ou seulement sur le
 * net à payer (retenue ou versement : acompte, net négatif reporté, trop-perçu,
 * avance). La gestionnaire tape toujours un montant positif ; le choix fixe le
 * signe et les cases envoyées. Le moteur lit `sur_le_net`, plus le libellé.
 */
export type SensSaisie = 'prime' | 'retenue_net' | 'versement_net';

export const SENS_SAISIE: { value: SensSaisie; libelle: string; aide: string }[] = [
  { value: 'prime', libelle: 'Prime', aide: 'Ajoutée au salaire brut, avec ses cotisations.' },
  {
    value: 'retenue_net',
    libelle: 'Retenue sur le net',
    aide: 'Acompte, net négatif reporté, trop-perçu… Retirée du net à payer, sans toucher au brut.',
  },
  {
    value: 'versement_net',
    libelle: 'Versement sur le net',
    aide: 'Avance… Ajoutée au net à payer, sans toucher au brut.',
  },
];

export interface ChampsSaisie {
  amount: number;
  sur_le_net: boolean;
  is_socially_taxed: boolean;
  is_taxable: boolean;
}

export function champsDeLaSaisie(
  sens: SensSaisie,
  montant: number,
  cases: { is_socially_taxed: boolean; is_taxable: boolean },
): ChampsSaisie {
  if (sens === 'prime') {
    return { amount: montant, sur_le_net: false, ...cases };
  }
  const valeur = Math.abs(montant);
  return {
    amount: sens === 'retenue_net' ? -valeur : valeur,
    sur_le_net: true,
    is_socially_taxed: false,
    is_taxable: false,
  };
}

/** Valeur proposée à la correction : toujours positive, le sens ne se change pas en tapant un signe. */
export function montantAEditer(amount: number): string {
  return String(Math.abs(amount));
}

/** Montant envoyé à la correction : celui qui est tapé, avec le sens de la saisie existante. */
export function montantAEnvoyer(ancien: number, saisi: number): number {
  return ancien < 0 ? -Math.abs(saisi) : Math.abs(saisi);
}

/** Le sens d'une retenue, dit en toutes lettres à côté du montant (négatif = retenue). */
export function libelleMontantSaisie(amount: number, _surLeNet: boolean): string | null {
  return amount < 0 ? 'Retenue sur le net' : null;
}

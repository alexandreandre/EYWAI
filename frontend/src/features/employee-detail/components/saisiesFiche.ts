/**
 * Une saisie du mois telle que la fiche du salarié la montre (onglet « Primes et
 * autres ») : ce que dit la page des primes — retenue ou versement sur le net,
 * heures sup déclarées au bulletin —, montants à la française.
 */
import { heuresDeclareesDeLaSaisie } from '@/components/saisies/libellesSaisie';
import { libelleMontantSaisie } from '@/components/saisies/sensSaisie';

export interface SaisieDeLaFiche {
  name: string;
  amount: number;
  is_socially_taxed: boolean;
  is_taxable: boolean;
  sur_le_net?: boolean | null;
  payroll_quantity?: number | null;
}

export interface PresentationSaisie {
  libelle: string;
  montant: string;
  pastille: string | null;
  cotisations: string;
  impot: string;
}

function euros(montant: number): string {
  const [entier, decimales] = Math.abs(montant).toFixed(2).split('.');
  const signe = montant < 0 ? '−' : '';
  return `${signe}${entier.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')},${decimales} €`;
}

export function presentationSaisieFiche(saisie: SaisieDeLaFiche): PresentationSaisie {
  const heures = heuresDeclareesDeLaSaisie(saisie);
  if (heures) {
    return { libelle: heures.libelle, montant: heures.quantite, pastille: null, cotisations: '—', impot: '—' };
  }
  const surLeNet = Boolean(saisie.sur_le_net);
  const pastille =
    libelleMontantSaisie(saisie.amount, surLeNet) ??
    (surLeNet && saisie.amount > 0 ? 'Versement sur le net' : null);
  return {
    libelle: saisie.name,
    montant: euros(saisie.amount),
    pastille,
    cotisations: surLeNet ? 'Sur le net' : saisie.is_socially_taxed ? 'Oui' : 'Non',
    impot: saisie.is_taxable ? 'Oui' : 'Non',
  };
}

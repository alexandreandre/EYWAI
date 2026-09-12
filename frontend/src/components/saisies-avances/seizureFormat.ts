import type { CalculationMode } from '@/api/saisiesAvances';

type SaisieMontant = {
  calculation_mode: CalculationMode;
  amount?: number | null;
  percentage?: number | null;
};

/**
 * Libellé du montant d'une saisie sur salaire.
 *
 * Les décimaux Postgres arrivent en chaîne via l'API (« 46.49 ») : on
 * convertit avant de formater. Appeler `toFixed` directement sur la valeur
 * faisait tomber toute la page Saisies sur salaire en écran blanc dès
 * qu'une saisie existait (Gautheron, 12/09).
 */
export function libelleMontantSaisie(saisie: SaisieMontant): string {
  if (saisie.calculation_mode === 'fixe' && saisie.amount) {
    const montant = Number(saisie.amount);
    if (Number.isFinite(montant)) return `${montant.toFixed(2)}€`;
  }
  if (saisie.calculation_mode === 'pourcentage' && saisie.percentage) {
    return `${saisie.percentage}%`;
  }
  return 'Barème légal';
}

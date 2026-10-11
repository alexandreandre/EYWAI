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
 * qu'une saisie existait (salarié 140, 12/09).
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

/**
 * Nombre de personnes à charge saisi dans le formulaire.
 *
 * Chacune relève les seuils du barème légal de la quotité saisissable
 * (R3252-3 du Code du travail) : un entier, jamais négatif ; vide ou illisible,
 * aucune.
 */
export function personnesACharge(texte: string): number {
  const nombre = Math.floor(Number(texte));
  return Number.isFinite(nombre) && nombre > 0 ? nombre : 0;
}

export function libellePersonnesACharge(nombre: number | null | undefined): string {
  const n = Number(nombre) || 0;
  if (n <= 0) return 'Aucune';
  return n === 1 ? '1 personne' : `${n} personnes`;
}

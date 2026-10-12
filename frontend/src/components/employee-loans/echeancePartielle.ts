/**
 * L'explication d'une échéance de prêt retenue en partie, pour le volet du
 * prêt : la même règle que l'alerte du bulletin (rejeu G.3, 11/10/2026).
 */

type Echeance = {
  installment_number: number;
  year: number;
  month: number;
  total_due: number;
  capital_paid?: number;
  interest_paid?: number;
  status: string;
};

const FORMAT_EUROS = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const centimes = (valeur: number) => Math.round(valeur * 100) / 100;

/** Une échéance entamée sans être soldée : « Partielle » au volet du prêt. */
export function estEcheancePartielle(echeance: Echeance): boolean {
  const preleve = (echeance.capital_paid ?? 0) + (echeance.interest_paid ?? 0);
  if (echeance.status === 'partial') return true;
  return echeance.status === 'pending' && preleve > 0;
}

/** Combien, sur combien, la règle et le sort du reliquat ; null sinon. */
export function explicationEcheancePartielle(echeance: Echeance): string | null {
  if (!estEcheancePartielle(echeance)) return null;
  const preleve = centimes((echeance.capital_paid ?? 0) + (echeance.interest_paid ?? 0));
  const reliquat = centimes(Math.max(0, echeance.total_due - preleve));
  const periode = `${String(echeance.month).padStart(2, '0')}/${echeance.year}`;
  return (
    `Échéance n° ${echeance.installment_number} (${periode}) : ` +
    `${FORMAT_EUROS.format(preleve)} retenus sur ${FORMAT_EUROS.format(echeance.total_due)} prévus. ` +
    'Chaque mois, la retenue est limitée au dixième du salaire exigible (article L3251-3 ' +
    "du Code du travail), dans la limite du net à payer ; l'alerte du bulletin donne le détail. " +
    `Le reliquat de ${FORMAT_EUROS.format(reliquat)} reste dû : il sera retenu seul sur le ` +
    "bulletin suivant, et les échéances suivantes glissent d'un mois."
  );
}

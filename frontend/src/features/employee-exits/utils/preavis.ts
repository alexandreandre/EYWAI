/**
 * Préavis d'un départ : trois cas, et « Non applicable ».
 *
 * Code du travail L1234-5 et service-public F2883 : un préavis exécuté est payé
 * avec le salaire ; une dispense à l'initiative de l'employeur ouvre
 * l'indemnité compensatrice ; une dispense demandée par le salarié et acceptée
 * ne donne rien. Les valeurs sont celles que lisent le calcul et les documents
 * (backend : payroll/engine/preavis.py).
 */
export type TypePreavis = 'executed' | 'paid' | 'waived' | 'not_applicable';

export const PREAVIS_PAR_DEFAUT: TypePreavis = 'executed';

export const OPTIONS_PREAVIS: { value: TypePreavis; label: string }[] = [
  { value: 'executed', label: 'Exécuté (payé avec le salaire)' },
  { value: 'paid', label: "Dispense à l'initiative de l'employeur (indemnité compensatrice)" },
  { value: 'waived', label: 'Dispense à la demande du salarié (aucune indemnité)' },
  { value: 'not_applicable', label: 'Non applicable' },
];

/** La valeur après l'aperçu du préavis : « Non applicable » sans préavis ;
 * sinon on garde le choix de la gestionnaire, et « exécuté » s'il n'y en avait pas. */
export function typePreavisApresApercu(
  apercu: { applicable: boolean; notice_period_days: number },
  actuel: TypePreavis
): TypePreavis {
  if (!apercu.applicable || apercu.notice_period_days === 0) return 'not_applicable';
  return actuel === 'not_applicable' ? PREAVIS_PAR_DEFAUT : actuel;
}

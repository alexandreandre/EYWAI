/**
 * Préavis d'un départ : trois cas, et « Non applicable ».
 *
 * Code du travail L1234-5 et service-public F2883 : un préavis exécuté est payé
 * avec le salaire ; une dispense à l'initiative de l'employeur ouvre
 * l'indemnité compensatrice ; une dispense demandée par le salarié et acceptée
 * ne donne rien. Les valeurs sont celles que lisent le calcul et les documents
 * (backend : payroll/engine/preavis.py).
 */
import { pluriel } from '@/lib/pluriel';

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

/** Après une durée saisie à la main : une durée fait passer « Non applicable »
 * à « Exécuté » ; aucune durée, « Non applicable ». (La loi ne fixe pas de
 * préavis de démission : la durée se saisit, F2883.) */
export function typePreavisApresSaisie(jours: number, actuel: TypePreavis): TypePreavis {
  if (!jours) return 'not_applicable';
  return actuel === 'not_applicable' ? PREAVIS_PAR_DEFAUT : actuel;
}

/** D'où vient la durée proposée. */
export function libelleSourcePreavis(source: string): string {
  switch (source) {
    case 'convention':
      return 'Convention collective';
    case 'legal':
      return 'Code du travail';
    case 'not_applicable':
      return 'Non applicable';
    case 'none':
      return 'à saisir : convention, contrat ou usage';
    default:
      return 'Non déterminé';
  }
}

/** Les départs dont l'écran saisit la durée et l'exécution du préavis : la
 * démission, le licenciement, le départ et la mise à la retraite (L1237-6 et
 * L1237-10 renvoient au préavis du licenciement, L1234-1). Une fin de période
 * d'essai n'a pas de préavis : son délai de prévenance se calcule. */
export function preavisASaisir(exitType: string): boolean {
  return exitType === 'demission' || exitType === 'licenciement' || exitType === 'depart_retraite';
}

/**
 * L'avertissement « dernier jour avant la fin du préavis », ou null.
 *
 * Seul un préavis EXÉCUTÉ va jusqu'à sa fin théorique : dispensé (par
 * l'employeur ou à la demande du salarié), il ne s'exécute pas et le dernier
 * jour peut tomber avant. L'avertissement restait affiché après le choix
 * d'une dispense (tournage H.2, scène 6).
 */
export function avertissementFinDePreavis({
  applicable,
  jours,
  dateDeDemande,
  dernierJour,
  execution,
}: {
  applicable: boolean | undefined;
  jours: number;
  dateDeDemande: string;
  dernierJour: string;
  execution: TypePreavis;
}): string | null {
  if (!applicable || jours <= 0 || !dernierJour || !dateDeDemande) return null;
  if (execution !== 'executed') return null;
  const finTheorique = new Date(dateDeDemande);
  finTheorique.setDate(finTheorique.getDate() + jours);
  if (!(new Date(dernierJour) < finTheorique)) return null;
  return `Le dernier jour travaillé est antérieur à la fin théorique du préavis (${pluriel(jours, 'jour')}). Vérifiez les dates ou indiquez une dispense.`;
}

/** La durée montrée dans son champ : vide pour zéro. Le champ partait de
 * « 0 » et taper « 60 » donnait « 060 » (tournage H.2, scène 4). */
export function dureePreavisAffichee(jours: number): string {
  return jours > 0 ? String(jours) : '';
}

/** La durée tapée, en jours entiers ; un champ vide vaut zéro. */
export function dureePreavisSaisie(texte: string): number {
  const jours = Number.parseInt(texte, 10);
  return Number.isNaN(jours) || jours < 0 ? 0 : jours;
}

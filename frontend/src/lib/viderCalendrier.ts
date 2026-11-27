/**
 * Vider un calendrier (retour d'Elsa : « un gros bouton rouge pour annuler un
 * modèle appliqué par erreur, et pouvoir supprimer des lignes
 * individuellement »).
 *
 * Vider remet le jour à vide, prévu et réel : il redevient « à saisir ». Les
 * arrêts, congés et absences posés restent : ils se retirent là où ils se
 * posent (Congés, Arrêts & IJ), sinon la demande validée et le planning se
 * contrediraient. Même liste que le serveur (`schedules.domain.vider_mois`).
 * Le vidage du mois est fait par le serveur, qui garde aussi les jours lus par
 * un bulletin validé.
 */
import type { PlannedEventData } from '@/api/calendar';
import type { DayPatch } from '@/lib/schedulesOverview';
import { accord, pluriel } from '@/lib/pluriel';

/** Types d'absence posée que le vidage ne touche jamais. */
export const TYPES_GARDES_AU_VIDAGE: ReadonlySet<string> = new Set([
  'arret_maladie',
  'conge',
  'conges_payes',
  'evenement_familial',
  'rtt',
  'absence_non_remuneree',
  'activite_partielle',
]);

export function jourGardeParLeVidage(planned: PlannedEventData | undefined): boolean {
  if (!planned) return false;
  return TYPES_GARDES_AU_VIDAGE.has(planned.type) || planned.origine === 'absence';
}

/** Type d'un jour vide : week-end le samedi et le dimanche, férié s'il l'était, sinon travail. */
export function typeDuJourVide(year: number, month: number, planned: PlannedEventData): string {
  if (planned.type === 'ferie') return 'ferie';
  const dow = new Date(year, month - 1, planned.jour).getDay();
  return dow === 0 || dow === 6 ? 'weekend' : 'travail';
}

export const REFUS_VIDER_ABSENCE =
  'Absence posée : elle se retire dans Congés ou Arrêts & IJ, pas en vidant le jour.';

/** Le patch qui vide un jour (prévu, réel, horaires), ou la raison du refus. */
export function viderLeJour(
  year: number,
  month: number,
  planned: PlannedEventData,
): { patch: DayPatch } | { refus: string } {
  if (jourGardeParLeVidage(planned)) return { refus: REFUS_VIDER_ABSENCE };
  return {
    patch: {
      type: typeDuJourVide(year, month, planned),
      heures_prevues: null,
      heures_faites: null,
      debut: null,
      fin: null,
    },
  };
}

export interface BilanVidage {
  joursVides: number;
  joursAbsence: number;
  joursBulletin: number;
  salaries: number;
  /** « octobre 2026 » */
  moisLabel: string;
}

function gardes(b: BilanVidage): string[] {
  const out: string[] = [];
  if (b.joursAbsence > 0) out.push(`${pluriel(b.joursAbsence, 'jour')} d’arrêt, de congé ou d’absence ${accord(b.joursAbsence, 'posé')}`);
  if (b.joursBulletin > 0) out.push(`${pluriel(b.joursBulletin, 'jour')} ${accord(b.joursBulletin, 'lu')} par un bulletin validé`);
  return out;
}

function deMois(moisLabel: string): string {
  return /^[aeiouyéèêàâîôû]/i.test(moisLabel) ? `d’${moisLabel}` : `de ${moisLabel}`;
}

export function phraseConfirmationVidage(b: BilanVidage): string {
  const restent = gardes(b);
  const suite = restent.length > 0 ? ` Restent tels quels : ${restent.join(' et ')}.` : '';
  if (b.joursVides === 0) {
    return `Rien à vider en ${b.moisLabel} : aucun jour saisi en dehors des absences posées et des bulletins validés.${suite}`;
  }
  const pour = b.salaries > 1 ? ` pour ${pluriel(b.salaries, 'salarié')}` : '';
  return `${pluriel(b.joursVides, 'jour')} ${deMois(b.moisLabel)} ${accord(b.joursVides, 'sera vidé', 'seront vidés')} (prévu et réel)${pour}.${suite}`;
}

export function phraseResultatVidage(b: BilanVidage): string {
  const restent = gardes(b);
  const pour = b.salaries > 1 ? ` pour ${pluriel(b.salaries, 'salarié')}` : '';
  const vides = b.joursVides > 1 ? 'vidés' : 'vidé';
  return `${pluriel(b.joursVides, 'jour')} ${vides} en ${b.moisLabel}${pour}.${
    restent.length > 0 ? ` Gardés : ${restent.join(' et ')}.` : ''
  }`;
}

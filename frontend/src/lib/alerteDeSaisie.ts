/**
 * Ce que dit une ligne du calendrier restée « à saisir » (retour du 10/11) :
 * le calendrier restait rouge sans dire quel jour bloquait. L'alerte nomme les
 * jours et la raison, rappelle la borne du mois (arrêté des variables, sortie)
 * et dit comment passer outre quand les jours sont justes tels quels : le
 * bulletin se génère quand même après confirmation (forçage tracé).
 */
import { phraseJoursASaisir, type JourASaisir } from '@/lib/calendarStats';

export interface LigneAAlerter {
  rowStatus: string;
  joursASaisir?: JourASaisir[];
  dernierJourJuge?: number | null;
  dernierJourContrat?: number | null;
}

export interface AlerteDeSaisie {
  /** « 27/10–28/10 (heures réelles non saisies) » */
  jours: string;
  /** Phrase complète, pour l'infobulle. */
  detail: string;
}

export function alerteDeSaisie(
  ligne: LigneAAlerter,
  year: number,
  month: number,
): AlerteDeSaisie | null {
  const manquants = ligne.joursASaisir ?? [];
  if (ligne.rowStatus !== 'a_saisir' || manquants.length === 0) return null;
  const mm = String(month).padStart(2, '0');
  const jj = (j: number) => `${String(j).padStart(2, '0')}/${mm}`;
  const jours = phraseJoursASaisir(manquants, month);
  const finDuMois = new Date(year, month, 0).getDate();
  let borne = '';
  if (ligne.dernierJourContrat != null && ligne.dernierJourContrat > 0 && ligne.dernierJourContrat < finDuMois) {
    borne = ` Rien n'est attendu après la sortie le ${jj(ligne.dernierJourContrat)}.`;
  } else if (ligne.dernierJourJuge != null && ligne.dernierJourJuge < finDuMois) {
    borne = ` Les jours après le ${jj(ligne.dernierJourJuge)} comptent pour le mois suivant (arrêté des variables).`;
  }
  const detail =
    `À compléter : ${jours}.${borne} Si ces jours sont justes tels quels, le bulletin se ` +
    'génère quand même : au lancement de la paie, choisissez « Générer quand même » ' +
    '(ces jours sont alors payés à plein).';
  return { jours, detail };
}

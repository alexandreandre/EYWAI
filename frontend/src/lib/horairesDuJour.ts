/**
 * Heure d'arrivée et de départ d'un jour, saisies à la main (retour d'Elsa du
 * 27/11 : « quand je rentre à la main 7 h, il faut pouvoir rentrer ses horaires
 * pour que ça déclenche un panier » — la règle panier LEWIS lit l'arrivée).
 *
 * Le serveur garde l'arrivée quand seules les heures changent ; une heure
 * envoyée est enregistrée, une heure envoyée vide est effacée
 * (`schedules.domain.horaires_pointes.garder_les_horaires`).
 */
import type { ActualHoursData } from '@/api/calendar';

export interface HorairesDuJour {
  debut: string | null;
  fin: string | null;
}

/**
 * Une heure tapée au clavier : « 7 », « 7h », « 07h00 », « 7:00 », « 0700 »
 * → « 07:00 ». Vide : `null`. Sinon « illisible » (dit à l'écran, jamais jeté).
 * Champ texte plutôt que le champ horaire du navigateur : celui-ci attend
 * AM/PM dans un navigateur réglé en anglais et reste vide sans le dire
 * (e2e 38 du 27/11).
 */
export function lireHeure(saisie: string): string | null | 'illisible' {
  const texte = saisie.trim().toLowerCase().replace(/\s+/g, '');
  if (!texte) return null;
  const m = texte.match(/^(\d{1,2})(?:[:h]?(\d{2}))?h?$/);
  if (!m) return 'illisible';
  const heures = Number(m[1]);
  const minutes = m[2] ? Number(m[2]) : 0;
  if (heures > 23 || minutes > 59) return 'illisible';
  return `${String(heures).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
}

export function horairesSaisis(saisie: {
  arrivee: string;
  depart: string;
  heuresFaites: string;
  /** Type du jour qui porte des heures (travail, samedi ou férié travaillé). */
  travaille: boolean;
}): { horaires: HorairesDuJour } | { refus: string } {
  if (!saisie.travaille) return { horaires: { debut: null, fin: null } };
  const debut = lireHeure(saisie.arrivee);
  const fin = lireHeure(saisie.depart);
  if (debut === 'illisible') return { refus: 'Heure d’arrivée illisible : tapez par exemple 07:00 ou 7h.' };
  if (fin === 'illisible') return { refus: 'Heure de départ illisible : tapez par exemple 15:30 ou 15h30.' };
  const heures = Number(saisie.heuresFaites.replace(',', '.'));
  if ((debut || fin) && !(saisie.heuresFaites.trim() !== '' && heures > 0)) {
    return {
      refus: 'Saisissez les heures faites : l’heure d’arrivée n’est gardée que sur un jour travaillé.',
    };
  }
  return { horaires: { debut, fin } };
}

/** « Arrivée 07:00 » pour la case du jour, ou `null`. */
export function libelleArrivee(jour: Pick<ActualHoursData, 'debut'> | undefined): string | null {
  return jour?.debut ? `Arrivée ${jour.debut}` : null;
}

/**
 * Le réel du mois tel que le calendrier du mois l'envoie : l'arrivée qu'il
 * connaît est renvoyée (une correction des heures à la main la garde), une
 * arrivée vidée part vide (le serveur l'efface). Le départ n'est renvoyé que
 * vidé : sinon le serveur le garde tant que les heures n'ont pas bougé.
 */
export function horairesAEnvoyer(jours: ActualHoursData[]): ActualHoursData[] {
  return jours.map(({ debut, fin, ...jour }) => ({
    ...jour,
    ...(debut !== undefined ? { debut: debut || null } : {}),
    ...(fin === null || fin === '' ? { fin: null } : {}),
  }));
}

/** Ce qui sera effacé sur un jour non travaillé, ou `null` s'il n'y a rien. */
export function noteHorairesJourNonTravaille(arrivee: string, depart: string): string | null {
  const a = arrivee.trim();
  const d = depart.trim();
  if (a && d) {
    return `Jour non travaillé : l’arrivée (${a}) et le départ (${d}) seront effacés à l’enregistrement.`;
  }
  if (a) return `Jour non travaillé : l’arrivée (${a}) sera effacée à l’enregistrement.`;
  if (d) return `Jour non travaillé : le départ (${d}) sera effacé à l’enregistrement.`;
  return null;
}

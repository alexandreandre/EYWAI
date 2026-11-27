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

export function horairesSaisis(saisie: {
  arrivee: string;
  depart: string;
  heuresFaites: string;
  /** Type du jour qui porte des heures (travail, samedi ou férié travaillé). */
  travaille: boolean;
}): { horaires: HorairesDuJour } | { refus: string } {
  const debut = saisie.arrivee.trim() || null;
  const fin = saisie.depart.trim() || null;
  if (!saisie.travaille) return { horaires: { debut: null, fin: null } };
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
 * Le réel du mois sans les horaires : le calendrier du mois ne les modifie pas,
 * le serveur garde ceux qu'il a (l'arrivée même si les heures changent).
 */
export function sansHoraires(jours: ActualHoursData[]): ActualHoursData[] {
  return jours.map(({ debut: _debut, fin: _fin, ...jour }) => jour);
}

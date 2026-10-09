/**
 * Lecture du pilotage de la saisie mensuelle (page Calendrier) : ce que l'écran
 * dit des heures saisies un jour d'arrêt, d'un filtre sans résultat et d'un écart.
 * Constats du 08/10/2026 : « prêts pour la paie » alors que la génération serait
 * refusée, « -105.0 h » d'écart sur un calendrier incomplet, « aucun employé ne
 * correspond » quand il ne reste simplement plus rien à saisir.
 */
import type { EmployeeRowStatus } from './calendarStats';

/**
 * Un salarié dont des jours portent des heures pendant un arrêt n'est pas prêt :
 * la génération sera refusée. Un calendrier encore à saisir reste « à saisir ».
 */
export function statutAvecHeuresSurArret(
  statut: EmployeeRowStatus,
  joursEnConflit: readonly number[] | undefined,
): EmployeeRowStatus {
  if (statut === 'saisi' && (joursEnConflit?.length ?? 0) > 0) return 'saisi_avec_ecart';
  return statut;
}

interface LigneAvecConflit {
  employee: { id: string; first_name: string; last_name: string };
  joursHeuresSurArret?: number[];
}

export interface ResumeHeuresSurArret {
  totalJours: number;
  salaries: { id: string; nom: string; jours: number[] }[];
}

export function resumeHeuresSurArret(rows: LigneAvecConflit[]): ResumeHeuresSurArret {
  const salaries = rows
    .filter((r) => (r.joursHeuresSurArret?.length ?? 0) > 0)
    .map((r) => ({
      id: r.employee.id,
      nom: `${r.employee.first_name} ${r.employee.last_name}`,
      jours: r.joursHeuresSurArret as number[],
    }));
  return { totalJours: salaries.reduce((n, s) => n + s.jours.length, 0), salaries };
}

export function phraseHeuresSurArret(resume: ResumeHeuresSurArret): string | null {
  if (resume.totalJours === 0) return null;
  const jours =
    resume.totalJours > 1 ? `${resume.totalJours} jours portent` : '1 jour porte';
  const noms = resume.salaries.map((s) => s.nom).join(', ');
  return `${jours} des heures pendant un arrêt ou une absence (${noms}) : la génération de la paie sera refusée tant qu’ils ne sont pas corrigés.`;
}

/** Ce que dit la liste quand le filtre de saisie ne laisse aucun calendrier. */
export function messageFiltreSansCalendrier(
  filtreSaisie: string,
  _totalCalendriers: number,
): { titre: string; detail: string } {
  if (filtreSaisie === 'a_saisir') {
    return {
      titre: 'Plus aucun calendrier à saisir',
      detail: 'Tous les calendriers de ce mois sont saisis.',
    };
  }
  return {
    titre: 'Aucun employé ne correspond à vos filtres',
    detail: 'Modifiez la recherche ou les filtres pour afficher des résultats.',
  };
}

/** Écart affiché : aucun tant que le calendrier n'est pas complet (le réel manquant n'est pas un écart). */
export function ecartAffiche(row: {
  rowStatus: EmployeeRowStatus;
  isForfaitJour: boolean;
  ecart: number;
}): string | null {
  if (row.rowStatus === 'a_saisir') return null;
  const signe = row.ecart >= 0 ? '+' : '';
  return row.isForfaitJour ? `${signe}${row.ecart} j` : `${signe}${row.ecart.toFixed(1)} h`;
}

/**
 * Lecture du pilotage de la saisie mensuelle (page Calendrier) : ce que l'écran
 * dit des heures saisies un jour d'arrêt, d'un filtre sans résultat et d'un écart.
 * Constats du 08/10/2026 : « prêts pour la paie » alors que la génération serait
 * refusée, « -105.0 h » d'écart sur un calendrier incomplet, « aucun employé ne
 * correspond » quand il ne reste simplement plus rien à saisir.
 */
import { aDesHeuresPointees, type EmployeeRowStatus } from './calendarStats';
import type { ActualHoursData } from '@/api/calendar';

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

/** Pastille du tiroir d'un salarié : « Saisi » n'est dit que sans heures sur un arrêt. */
export function pastilleSaisieDuMois(
  statut: 'saisi' | 'a_saisir' | string,
  joursEnConflit: readonly number[] | undefined,
): string {
  if (statut !== 'saisi') return 'À saisir';
  return (joursEnConflit?.length ?? 0) > 0 ? 'Heures sur un arrêt' : 'Saisi';
}

/**
 * Phrase de l'en-tête de page : prêt pour la paie seulement sans reste à saisir
 * ni conflit. Un calendrier qui porte des heures sur un arrêt n'est pas prêt
 * non plus : il compte dans le reste, et l'alerte ambre le dit même quand
 * d'autres calendriers sont encore à saisir (tournage C1 du 18/10 : « Reste à
 * compléter : 1 calendrier sur 4 », sans un mot du calendrier en conflit).
 */
export function libelleEntetePilotage(k: {
  aSaisir: number;
  avecHeuresSurArret: number;
  total: number;
  /** Saisis et sans conflit ; à défaut, le reste vaut à saisir + en conflit. */
  prets?: number;
  /** Prêts parce que, sans heure pointée, la paie reprend le prévu. */
  pretsSansHeuresPointees?: number;
}): { ton: 'ok' | 'alerte' | 'neutre'; texte: string } {
  const calendriers = (n: number) => `${n} calendrier${n > 1 ? 's' : ''}`;
  if (k.avecHeuresSurArret > 0) {
    const n = k.avecHeuresSurArret;
    if (k.aSaisir > 0) {
      const restants = k.prets !== undefined ? k.total - k.prets : k.aSaisir + n;
      return {
        ton: 'alerte',
        texte: `Reste à compléter : ${calendriers(restants)} sur ${k.total}, dont ${n} qui ${
          n > 1 ? 'portent' : 'porte'
        } des heures pendant un arrêt : à corriger avant la paie`,
      };
    }
    return {
      ton: 'alerte',
      texte: `${calendriers(n)} ${n > 1 ? 'portent' : 'porte'} des heures pendant un arrêt : à corriger avant la paie`,
    };
  }
  if (k.aSaisir > 0) {
    return { ton: 'neutre', texte: `Reste à compléter : ${calendriers(k.aSaisir)} sur ${k.total}` };
  }
  // Sans aucune heure pointée, un calendrier est « prêt » parce que la paie
  // reprend son prévu : le dire (tournage C1 du 18/10, réel vide pendant
  // l'import des pointages, « Tous les calendriers sont prêts »).
  const sans = k.pretsSansHeuresPointees ?? 0;
  if (sans > 0 && sans >= (k.prets ?? k.total)) {
    return {
      ton: 'neutre',
      texte: `Aucune heure pointée ce mois : la paie reprendra le prévu ${
        sans > 1 ? `des ${sans} calendriers` : 'du calendrier'
      }`,
    };
  }
  if (sans > 0) {
    return {
      ton: 'ok',
      texte: `Tous les calendriers sont prêts pour la paie (${sans} sans heure pointée : la paie reprend ${
        sans > 1 ? 'leur' : 'son'
      } prévu)`,
    };
  }
  return { ton: 'ok', texte: 'Tous les calendriers sont prêts pour la paie' };
}

/**
 * Le bandeau quand tous les calendriers affichés sont saisis, sans conflit.
 * « Prêts » ne se dit sans réserve que s'ils portent des heures pointées ;
 * sinon la paie reprendra le prévu, et des pointages restent peut-être à importer.
 */
export function bandeauCalendriersPrets(
  rows: readonly { isForfaitJour: boolean; actual: readonly ActualHoursData[] }[],
): { ton: 'ok' | 'neutre'; texte: string } {
  const sans = rows.filter((r) => !r.isForfaitJour && !aDesHeuresPointees(r.actual)).length;
  if (sans > 0 && sans === rows.length) {
    return {
      ton: 'neutre',
      texte:
        'Aucune heure pointée ce mois sur les calendriers affichés : la paie reprendra leur prévu. ' +
        'Si des pointages existent, importez-les avant de lancer la paie.',
    };
  }
  const precision =
    sans > 0 ? ` (${sans} sans heure pointée : la paie reprend ${sans > 1 ? 'leur' : 'son'} prévu)` : '';
  return {
    ton: 'ok',
    texte: `Tous les calendriers affichés sont prêts pour la paie ce mois-ci${precision}. Vous pouvez lancer le calcul de paie.`,
  };
}

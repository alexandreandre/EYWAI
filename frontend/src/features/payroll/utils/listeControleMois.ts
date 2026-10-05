/**
 * Liste de contrôle du mois de paie : une étape n'est cochée que si une
 * donnée le prouve. L'écran n'affiche que le résultat.
 *
 * Absences : aucun signal ne dit que toutes les absences du mois sont
 * saisies. L'étape reste à confirmer par la gestionnaire.
 *
 * Les deux dernières étapes disent que le mois est fini : bulletins validés,
 * DSN et export comptable faits (revue du 05/10 : rien ne le disait).
 */

import {
  MENTION_RIB_A_COMPLETER,
  mentionsListeSalarie,
} from '@/features/employees/utils/creationSalarie';
import { payrollEmploymentBlockReason } from '@/features/payroll/utils/employmentPeriod';
import { estPerime, type LigneBulletinPaie } from '@/features/payroll/utils/bulletinARecalculer';
import { estBulletinImporte } from '@/features/payroll/utils/bulletinImporte';
import {
  bandeauxSortieDuMois,
  type DepartPourSortieGuidee,
  type SalariePourSortieGuidee,
} from '@/features/payroll/utils/sortieGuidee';

export const ETAPE_CALENDRIERS = 'calendriers';
export const ETAPE_CONFLITS = 'conflits';
export const ETAPE_ABSENCES = 'absences';
export const ETAPE_BULLETINS = 'bulletins';
export const ETAPE_SORTIES = 'sorties';
export const ETAPE_RIB = 'rib';
export const ETAPE_VALIDES = 'valides';
export const ETAPE_DECLARATIONS = 'declarations';

/** Les exports qui comptent comme « export comptable » du mois. */
export const TYPES_EXPORT_COMPTABLE: readonly string[] = [
  'od_globale',
  'od_salaires',
  'od_charges_sociales',
  'od_pas',
  'export_cabinet_generique',
  'export_cabinet_quadra',
  'export_cabinet_sage',
  'fec',
];
export const TYPE_EXPORT_DSN = 'dsn_mensuelle';

export const MESSAGE_ABSENCES_A_CONFIRMER =
  'Le logiciel ne peut pas vérifier que toutes les absences du mois sont saisies. Confirmez-le vous-même dans Congés & absences.';

export const MESSAGE_REVUE_ACTIFS_SEULEMENT =
  'Le contrôle automatique ne porte que les salariés actifs et en sortie. Vérifiez aussi les embauches en cours.';

export type EtatEtape = 'fait' | 'a_faire' | 'a_confirmer' | 'inconnu';

export type Lecture<T> =
  | { statut: 'chargement' }
  | { statut: 'erreur' }
  | { statut: 'ok'; valeur: T }
  | { statut: 'indisponible' };

export type SalariePourListeControle = SalariePourSortieGuidee & {
  hire_date?: string | null;
  date_debut_execution?: string | null;
};

export type EtapeControle = {
  id: string;
  libelle: string;
  etat: EtatEtape;
  detail: string;
};

export type ActionEnAttente = {
  id: string;
  quoi: string;
  ouCliquer: string;
  href: string;
  ensuite: string;
};

export type ListeControleMois = {
  etapes: EtapeControle[];
  actions: ActionEnAttente[];
};

/** Une ligne de l'historique des exports du mois (GET /api/exports/history?period=). */
export type ExportPourControle = {
  export_type: string;
  status: string;
  generated_at: string;
  a_refaire?: boolean;
};

export type EntreeListeControle = {
  year: number;
  month: number;
  salaries: readonly SalariePourListeControle[];
  lectureSalaries?: Lecture<readonly SalariePourListeControle[]>;
  bulletinsParSalarie: Lecture<Record<string, LigneBulletinPaie[]>>;
  departs: Lecture<readonly DepartPourSortieGuidee[]>;
  calendriersASaisir: Lecture<readonly string[]>;
  conflitsArret: Lecture<readonly string[]>;
  /** Absent : non lu, l'étape reste à confirmer. */
  exportsDuMois?: Lecture<readonly ExportPourControle[]>;
};

type AnomalieCalendrier = {
  type?: string;
  status?: string;
  employee_id?: string;
  jours_manquants?: string[] | null;
};

type ConflitPreflight = {
  employee_id?: string;
  jours?: unknown;
};

function idsDuMois(ids: readonly string[], salaries: readonly SalariePourListeControle[]): string[] {
  const connus = new Set(salaries.map((s) => s.id));
  return ids.filter((id) => connus.has(id));
}

/** La revue pré-paie lit les salariés actifs et en sortie (départ créé, dernier bulletin à faire). */
const STATUTS_DE_LA_REVUE = new Set(['actif', 'en_sortie']);

function aDesSalariesHorsRevue(salaries: readonly SalariePourListeControle[]): boolean {
  return salaries.some((s) => !STATUTS_DE_LA_REVUE.has((s.employment_status || 'actif').trim().toLowerCase()));
}

function etatDepuisLecture<T>(
  lecture: Lecture<T>,
  quandOk: (valeur: T) => { etat: EtatEtape; detail: string }
): { etat: EtatEtape; detail: string } {
  if (lecture.statut === 'chargement') {
    return { etat: 'inconnu', detail: 'Vérification en cours.' };
  }
  if (lecture.statut === 'erreur' || lecture.statut === 'indisponible') {
    return {
      etat: 'a_confirmer',
      detail: 'Cette étape n’a pas pu être vérifiée. Ne la considérez pas comme faite.',
    };
  }
  return quandOk(lecture.valeur);
}

function pluriel(n: number, un: string, plusieurs: string): string {
  return n <= 1 ? un : plusieurs;
}

function lienMois(year: number, month: number): string {
  return `/payroll?view=month&month=${year}-${String(month).padStart(2, '0')}`;
}

function etapeCalendriers(
  lecture: Lecture<readonly string[]>,
  salaries: readonly SalariePourListeControle[]
): { etat: EtatEtape; detail: string } {
  return etatDepuisLecture(lecture, (ids) => {
    const n = idsDuMois(ids, salaries).length;
    if (n === 0) {
      if (aDesSalariesHorsRevue(salaries)) {
        return { etat: 'a_confirmer', detail: MESSAGE_REVUE_ACTIFS_SEULEMENT };
      }
      return { etat: 'fait', detail: 'Tous les calendriers du mois sont complets.' };
    }
    return {
      etat: 'a_faire',
      detail: pluriel(
        n,
        '1 calendrier a encore des jours à saisir.',
        `${n} calendriers ont encore des jours à saisir.`
      ),
    };
  });
}

function etapeConflits(
  lecture: Lecture<readonly string[]>,
  salaries: readonly SalariePourListeControle[]
): { etat: EtatEtape; detail: string } {
  return etatDepuisLecture(lecture, (ids) => {
    const n = idsDuMois(ids, salaries).length;
    if (n === 0) {
      if (aDesSalariesHorsRevue(salaries)) {
        return { etat: 'a_confirmer', detail: MESSAGE_REVUE_ACTIFS_SEULEMENT };
      }
      return { etat: 'fait', detail: 'Aucune heure saisie un jour d’arrêt.' };
    }
    return {
      etat: 'a_faire',
      detail: pluriel(
        n,
        '1 salarié a des heures saisies un jour d’arrêt.',
        `${n} salariés ont des heures saisies un jour d’arrêt.`
      ),
    };
  });
}

function etapeBulletins(
  lecture: Lecture<Record<string, LigneBulletinPaie[]>>,
  salaries: readonly SalariePourListeControle[],
  year: number,
  month: number
): { etat: EtatEtape; detail: string } {
  return etatDepuisLecture(lecture, (parSalarie) => {
    let manquants = 0;
    let perimes = 0;
    for (const salarie of salaries) {
      if (payrollEmploymentBlockReason(salarie, year, month)) continue;
      const ligne = (parSalarie[salarie.id] ?? []).find((p) => p.year === year && p.month === month);
      if (!ligne) {
        manquants += 1;
        continue;
      }
      if (estPerime(ligne)) perimes += 1;
    }
    if (manquants === 0 && perimes === 0) {
      return { etat: 'fait', detail: 'Les bulletins du mois sont générés et à jour.' };
    }
    const morceaux: string[] = [];
    if (manquants > 0) {
      morceaux.push(
        pluriel(manquants, '1 bulletin manque.', `${manquants} bulletins manquent.`)
      );
    }
    if (perimes > 0) {
      morceaux.push(
        pluriel(
          perimes,
          '1 bulletin est à recalculer.',
          `${perimes} bulletins sont à recalculer.`
        )
      );
    }
    return { etat: 'a_faire', detail: morceaux.join(' ') };
  });
}

function etapeSorties(
  lecture: Lecture<readonly DepartPourSortieGuidee[]>,
  salaries: readonly SalariePourListeControle[],
  year: number,
  month: number
): { etat: EtatEtape; detail: string } {
  return etatDepuisLecture(lecture, (departs) => {
    const aCreer = bandeauxSortieDuMois(salaries, departs, year, month).filter(
      (b) => b.etape === 'creer_depart'
    );
    if (aCreer.length === 0) {
      return { etat: 'fait', detail: 'Les départs du mois ont un dossier.' };
    }
    return {
      etat: 'a_faire',
      detail: pluriel(
        aCreer.length,
        '1 salarié part ce mois-ci sans dossier de départ.',
        `${aCreer.length} salariés partent ce mois-ci sans dossier de départ.`
      ),
    };
  });
}

function etapeValides(
  lecture: Lecture<Record<string, LigneBulletinPaie[]>>,
  salaries: readonly SalariePourListeControle[],
  year: number,
  month: number
): { etat: EtatEtape; detail: string } {
  return etatDepuisLecture(lecture, (parSalarie) => {
    let aValider = 0;
    for (const salarie of salaries) {
      if (payrollEmploymentBlockReason(salarie, year, month)) continue;
      const ligne = (parSalarie[salarie.id] ?? []).find((p) => p.year === year && p.month === month);
      // Un bulletin repris de l'ancien logiciel a été payé : rien à valider.
      if (ligne && (ligne.status === 'valide' || estBulletinImporte(ligne))) continue;
      aValider += 1;
    }
    if (aValider === 0) {
      return { etat: 'fait', detail: 'Les bulletins du mois sont validés.' };
    }
    return {
      etat: 'a_faire',
      detail: pluriel(
        aValider,
        '1 bulletin reste à valider.',
        `${aValider} bulletins restent à valider.`
      ),
    };
  });
}

/** Le dernier export généré de ces types : fait, à refaire, ou absent. */
function etatExport(
  exports: readonly ExportPourControle[],
  types: readonly string[]
): 'fait' | 'a_refaire' | 'absent' {
  const derniers = new Map<string, ExportPourControle>();
  for (const e of exports) {
    if (e.status !== 'generated' || !types.includes(e.export_type)) continue;
    const avant = derniers.get(e.export_type);
    if (!avant || e.generated_at > avant.generated_at) derniers.set(e.export_type, e);
  }
  if (derniers.size === 0) return 'absent';
  return [...derniers.values()].some((e) => e.a_refaire) ? 'a_refaire' : 'fait';
}

function etapeDeclarations(
  lecture: Lecture<readonly ExportPourControle[]>
): { etat: EtatEtape; detail: string } {
  return etatDepuisLecture(lecture, (exports) => {
    const dsn = etatExport(exports, [TYPE_EXPORT_DSN]);
    const compta = etatExport(exports, TYPES_EXPORT_COMPTABLE);
    if (dsn === 'fait' && compta === 'fait') {
      return { etat: 'fait', detail: 'La DSN et l’export comptable du mois sont faits.' };
    }
    const morceaux: string[] = [];
    if (dsn === 'absent') morceaux.push('La DSN du mois n’est pas faite.');
    if (dsn === 'a_refaire') morceaux.push('La DSN est à refaire : un bulletin du mois a changé depuis.');
    if (compta === 'absent') morceaux.push('L’export comptable du mois n’est pas fait.');
    if (compta === 'a_refaire') {
      morceaux.push('L’export comptable est à refaire : un bulletin du mois a changé depuis.');
    }
    return { etat: 'a_faire', detail: morceaux.join(' ') };
  });
}

function salariesSansRib(salaries: readonly SalariePourListeControle[]): SalariePourListeControle[] {
  return salaries.filter((s) =>
    mentionsListeSalarie(s.missing_payroll_fields).includes(MENTION_RIB_A_COMPLETER)
  );
}

function etapeRib(salaries: readonly SalariePourListeControle[]): { etat: EtatEtape; detail: string } {
  const n = salariesSansRib(salaries).length;
  if (n === 0) {
    return { etat: 'fait', detail: 'Les RIB du mois sont renseignés.' };
  }
  return {
    etat: 'a_faire',
    detail: pluriel(
      n,
      `1 salarié a la mention « ${MENTION_RIB_A_COMPLETER} ».`,
      `${n} salariés ont la mention « ${MENTION_RIB_A_COMPLETER} ».`
    ),
  };
}

function actionSiNonFaite(
  etape: EtapeControle,
  action: Omit<ActionEnAttente, 'id'>
): ActionEnAttente | null {
  if (etape.etat === 'fait' || etape.etat === 'inconnu') return null;
  return { id: etape.id, ...action };
}

export function listeControleDuMois(entree: EntreeListeControle): ListeControleMois {
  const { year, month, salaries } = entree;
  const hrefMois = lienMois(year, month);
  const lectureSalaries = entree.lectureSalaries ?? { statut: 'ok', valeur: salaries };

  const selonSalaries = (etape: EtapeControle): EtapeControle => {
    if (lectureSalaries.statut === 'ok') return etape;
    return { ...etape, ...etatDepuisLecture(lectureSalaries, () => etape) };
  };

  const calendriers = selonSalaries({
    id: ETAPE_CALENDRIERS,
    libelle: 'Calendriers complets',
    ...etapeCalendriers(entree.calendriersASaisir, salaries),
  });
  const conflits = selonSalaries({
    id: ETAPE_CONFLITS,
    libelle: 'Aucun conflit arrêt / heures',
    ...etapeConflits(entree.conflitsArret, salaries),
  });
  const absences: EtapeControle = {
    id: ETAPE_ABSENCES,
    libelle: 'Absences saisies',
    etat: 'a_confirmer',
    detail: MESSAGE_ABSENCES_A_CONFIRMER,
  };
  const bulletins = selonSalaries({
    id: ETAPE_BULLETINS,
    libelle: 'Bulletins générés et à jour',
    ...etapeBulletins(entree.bulletinsParSalarie, salaries, year, month),
  });
  const sorties = selonSalaries({
    id: ETAPE_SORTIES,
    libelle: 'Sorties créées',
    ...etapeSorties(entree.departs, salaries, year, month),
  });
  const rib = selonSalaries({
    id: ETAPE_RIB,
    libelle: 'RIB renseignés',
    ...etapeRib(salaries),
  });
  const valides = selonSalaries({
    id: ETAPE_VALIDES,
    libelle: 'Bulletins validés',
    ...etapeValides(entree.bulletinsParSalarie, salaries, year, month),
  });
  const declarations: EtapeControle = {
    id: ETAPE_DECLARATIONS,
    libelle: 'DSN et export comptable faits',
    ...etapeDeclarations(entree.exportsDuMois ?? { statut: 'indisponible' }),
  };

  const etapes = [calendriers, conflits, absences, bulletins, sorties, rib, valides, declarations];

  const actions = [
    actionSiNonFaite(calendriers, {
      quoi: 'Complétez les jours encore à saisir dans les calendriers.',
      ouCliquer: 'Calendrier',
      href: '/schedules',
      ensuite: 'Plus aucun jour de la fenêtre n’est marqué à saisir.',
    }),
    actionSiNonFaite(conflits, {
      quoi: 'Réglez les heures saisies un jour d’arrêt.',
      ouCliquer: 'Calendrier',
      href: '/schedules',
      ensuite:
        'Le bandeau propose d’effacer ces heures ou de modifier l’arrêt. Après correction, le conflit disparaît.',
    }),
    actionSiNonFaite(absences, {
      quoi: 'Vérifiez que chaque absence du mois est bien saisie.',
      ouCliquer: 'Congés & absences',
      href: '/leaves',
      ensuite: 'Chaque arrêt et congé du mois figure dans la liste. Le logiciel ne le coche pas à votre place.',
    }),
    actionSiNonFaite(bulletins, {
      quoi: 'Générez les bulletins manquants, puis recalculez ceux qui ont changé.',
      ouCliquer: 'Bulletins de paie, onglet Par mois',
      href: hrefMois,
      ensuite: 'Chaque salarié du mois a un bulletin, sans badge « À recalculer ».',
    }),
    actionSiNonFaite(sorties, {
      quoi: 'Créez le dossier de départ du salarié qui part ce mois-ci.',
      ouCliquer: 'Bulletins de paie, onglet Par mois',
      href: hrefMois,
      ensuite: 'Le bandeau « créez son départ » disparaît.',
    }),
    actionSiNonFaite(rib, {
      quoi: `Complétez le RIB des fiches qui portent « ${MENTION_RIB_A_COMPLETER} ».`,
      ouCliquer: 'Collaborateurs, fiche du salarié',
      href: '/employees',
      ensuite: `La mention « ${MENTION_RIB_A_COMPLETER} » disparaît de la liste.`,
    }),
    actionSiNonFaite(valides, {
      quoi: 'Validez les bulletins du mois.',
      ouCliquer: 'Bulletins de paie, onglet Par mois',
      href: hrefMois,
      ensuite:
        'Le bouton « Valider les bulletins prêts » valide ceux qui n’ont rien à revoir ; les autres se valident depuis leur bulletin. Chaque ligne porte « Validé ».',
    }),
    actionSiNonFaite(declarations, {
      quoi: 'Faites la DSN du mois et l’export comptable.',
      ouCliquer: 'Exports',
      href: '/exports',
      ensuite: 'La DSN mensuelle et l’export comptable du mois figurent dans l’historique, sans « à refaire ».',
    }),
  ].filter((a): a is ActionEnAttente => a !== null);

  return { etapes, actions };
}

/** La phrase sous le titre de la liste : ce qui reste, ou que le mois est fini. */
export function phraseListeControle(liste: ListeControleMois): string {
  const aFaire = liste.etapes.filter((e) => e.etat === 'a_faire').length;
  if (aFaire > 0) {
    return `${aFaire} point${aFaire > 1 ? 's' : ''} à traiter, d’après les données.`;
  }
  const restantes = liste.etapes.filter((e) => e.etat !== 'fait');
  if (restantes.length === 1 && restantes[0]?.id === ETAPE_ABSENCES) {
    return 'Paie du mois terminée : bulletins validés, DSN et export comptable faits. Confirmez vous-même que les absences étaient toutes saisies.';
  }
  if (restantes.some((e) => e.etat === 'a_confirmer')) {
    return 'Rien n’est coché sans preuve. Confirmez ce que le logiciel ne peut pas vérifier.';
  }
  return 'Les étapes vérifiables sont à jour.';
}

export function lectureCalendriersASaisir(preflight: {
  chargement: boolean;
  erreur: boolean;
  anomalies?: AnomalieCalendrier[] | null;
}): Lecture<string[]> {
  if (preflight.erreur) return { statut: 'erreur' };
  if (preflight.chargement && preflight.anomalies == null) return { statut: 'chargement' };
  const ids = (preflight.anomalies ?? [])
    .filter(
      (a) =>
        a.type === 'heures_non_saisies' &&
        typeof a.employee_id === 'string' &&
        (a.jours_manquants?.length ?? 0) > 0
    )
    .map((a) => a.employee_id as string);
  return { statut: 'ok', valeur: [...new Set(ids)] };
}

export function lectureConflitsArret(preflight: {
  chargement: boolean;
  erreur: boolean;
  heures_sur_arret?: ConflitPreflight[] | null;
}): Lecture<string[]> {
  if (preflight.chargement && preflight.heures_sur_arret === undefined && !preflight.erreur) {
    return { statut: 'chargement' };
  }
  if (preflight.erreur) return { statut: 'erreur' };
  if (preflight.heures_sur_arret === undefined || preflight.heures_sur_arret === null) {
    return { statut: 'indisponible' };
  }
  const ids = preflight.heures_sur_arret
    .filter((s) => typeof s.employee_id === 'string' && s.employee_id && Array.isArray(s.jours) && s.jours.length > 0)
    .map((s) => s.employee_id as string);
  return { statut: 'ok', valeur: [...new Set(ids)] };
}

/** Libellés et couleurs partagés — calendrier paie (RH et employé).
 *
 * SOURCE UNIQUE : toutes les vues (semaine équipe, calendrier complet,
 * popup jour, légendes) doivent consommer ces maps — congé en vert, arrêt
 * en rouge, partout pareil (demande Gaëlle 03/09). `conges_payes` et `rtt`
 * sont les types que la validation d'absence écrit côté backend
 * (ABSENCE_TYPE_TO_CALENDAR_TYPE) ; `work` est l'alias écrit par
 * l'application de modèle de semaine. */

export const CALENDAR_TYPE_LABELS: Record<string, string> = {
  travail: 'Travail',
  work: 'Travail',
  conge: 'Congé',
  conges_payes: 'Congés payés',
  rtt: 'RTT',
  ferie: 'Férié',
  arret_maladie: 'Arrêt maladie',
  weekend: 'Week-end',
  repos: 'Repos',
  // Types posés par les reprises DSN : sans libellé ni édition, un jour
  // « absence non rémunérée » hérité était invisible et incorrigible
  // (cas Marion 30/06, retour Gaëlle 07/09).
  absence_non_remuneree: 'Absence non rémunérée',
  absence_justifiee: 'Absence justifiée',
  ecole: 'École',
  // Case « absent » de l'import (retour d'Elsa du 28/10) : rouge vif, bloque la paie.
  absent_a_typer: 'Absent — type à donner',
  activite_partielle: 'Activité partielle',
};

export const CALENDAR_TYPE_BAR_COLORS: Record<string, string> = {
  travail: 'bg-sky-500',
  work: 'bg-sky-500',
  conge: 'bg-green-500',
  conges_payes: 'bg-green-500',
  rtt: 'bg-teal-500',
  ferie: 'bg-purple-500',
  arret_maladie: 'bg-red-500',
  weekend: 'bg-slate-400',
  repos: 'bg-slate-400',
  absence_non_remuneree: 'bg-orange-500',
  absence_justifiee: 'bg-amber-500',
  ecole: 'bg-indigo-500',
  absent_a_typer: 'bg-red-600',
  activite_partielle: 'bg-yellow-500',
};

/** Fonds de cellule/carte teintés par type (mêmes teintes que la vue semaine). */
export const CALENDAR_TYPE_BG_COLORS: Record<string, string> = {
  travail: 'bg-sky-50 hover:bg-sky-100 border-sky-200/60',
  work: 'bg-sky-50 hover:bg-sky-100 border-sky-200/60',
  conge: 'bg-green-50 hover:bg-green-100 border-green-200/60',
  conges_payes: 'bg-green-50 hover:bg-green-100 border-green-200/60',
  rtt: 'bg-teal-50 hover:bg-teal-100 border-teal-200/60',
  ferie: 'bg-purple-50 hover:bg-purple-100 border-purple-200/60',
  arret_maladie: 'bg-red-50 hover:bg-red-100 border-red-200/60',
  weekend: 'bg-slate-50 hover:bg-slate-100 border-slate-200/60',
  repos: 'bg-slate-50 hover:bg-slate-100 border-slate-200/60',
  absence_non_remuneree: 'bg-orange-50 hover:bg-orange-100 border-orange-200/60',
  absence_justifiee: 'bg-amber-50 hover:bg-amber-100 border-amber-200/60',
  ecole: 'bg-indigo-50 hover:bg-indigo-100 border-indigo-200/60',
  absent_a_typer: 'bg-red-100 hover:bg-red-200 border-red-500 ring-2 ring-red-500',
  activite_partielle: 'bg-yellow-50 hover:bg-yellow-100 border-yellow-200/60',
};

/**
 * Heures prévues et réelles d'une case : « Prévu » en orange, « Réel » en
 * vert-bleu, tous deux distincts du bleu du type « Travail » (retour d'Elsa
 * du 28/10 : « Travail » et « Prévu » avaient le même bleu).
 */
export const COULEUR_PREVU = {
  texte: 'text-orange-700',
  texteSombre: 'dark:text-orange-300',
  barre: 'bg-orange-500',
  piste: 'bg-orange-100/90',
} as const;

export const COULEUR_REEL = {
  texte: 'text-teal-700',
  texteSombre: 'dark:text-teal-300',
  barre: 'bg-teal-500',
  piste: 'bg-teal-100/90',
} as const;

export const CALENDAR_LEGEND_ITEMS: {
  key: string;
  label: string;
  colorClass: string;
}[] = [
  { key: 'travail', label: 'Travail', colorClass: 'bg-sky-500' },
  { key: 'conge', label: 'Congé', colorClass: 'bg-green-500' },
  { key: 'rtt', label: 'RTT', colorClass: 'bg-teal-500' },
  { key: 'ferie', label: 'Férié', colorClass: 'bg-purple-500' },
  { key: 'arret_maladie', label: 'Arrêt maladie', colorClass: 'bg-red-500' },
  { key: 'weekend', label: 'Week-end', colorClass: 'bg-slate-400' },
  { key: 'repos', label: 'Repos / récupération externe', colorClass: 'bg-slate-400' },
  { key: 'ecole', label: 'École', colorClass: 'bg-indigo-500' },
  { key: 'absent_a_typer', label: 'Absent, type à donner', colorClass: 'bg-red-600' },
  { key: 'today', label: "Aujourd'hui", colorClass: 'ring-2 ring-primary' },
];

/** Types proposés à la SAISIE d'un jour par la RH — source unique des
 * sélecteurs (cellule calendrier, panneau bulk, éditeur vue semaine).
 *
 * `conges_payes` et `rtt` déclenchent côté serveur la création automatique
 * d'une demande d'absence VALIDÉE (« une saisie RH enregistre un fait ») :
 * soldes décomptés et bulletin alimentés. L'ancien type `conge` est déprécié
 * à la saisie — il n'atteint ni la paie ni les soldes — et n'apparaît que
 * pour retyper un jour historique qui le porte encore. */
export const CALENDAR_EDITABLE_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: 'travail', label: 'Travail' },
  { value: 'conges_payes', label: 'Congés payés' },
  { value: 'rtt', label: 'RTT' },
  { value: 'ferie', label: 'Férié' },
  { value: 'weekend', label: 'Week-end' },
  { value: 'repos', label: 'Repos / récupération externe' },
  { value: 'absence_non_remuneree', label: 'Absence non rémunérée' },
  { value: 'ecole', label: 'École' },
];

/** Types qu'une COPIE de mois ne doit jamais répliquer : les jours CP/RTT du
 * mois source viennent de demandes validées — les recopier créerait autant de
 * nouvelles demandes validées (la saisie calendrier en matérialise une par
 * jour) ; l'ancien `conge` (hors paie) ne doit plus se propager. */
export const NON_COPYABLE_DAY_TYPES: ReadonlySet<string> = new Set([
  'conges_payes',
  'rtt',
  'conge',
  'ecole',
]);

/** Jour chômé d'activité partielle : proposé seulement quand la société l'a
 * activée (Paramètres, Paie). Le bulletin en tire la retenue et l'indemnité. */
export const OPTION_ACTIVITE_PARTIELLE = { value: 'activite_partielle', label: 'Activité partielle' };

/** Types proposés à la saisie, avec l'activité partielle si la société l'a activée. */
export function typesDeSaisie(activitePartielle = false): { value: string; label: string }[] {
  return activitePartielle
    ? [...CALENDAR_EDITABLE_TYPE_OPTIONS, OPTION_ACTIVITE_PARTIELLE]
    : CALENDAR_EDITABLE_TYPE_OPTIONS;
}

/** Option « Congé (hors paie) » ajoutée uniquement quand le jour la porte déjà.
 * « Activité partielle » : proposée quand la société l'a activée, ou quand le
 * jour la porte déjà (pour pouvoir le retyper). */
export function editableTypeOptionsFor(
  currentType: string | null | undefined,
  activitePartielle = false,
): { value: string; label: string }[] {
  let options = CALENDAR_EDITABLE_TYPE_OPTIONS;
  if (currentType === 'conge') {
    options = [...options, { value: 'conge', label: 'Congé (hors paie)' }];
  }
  // Un arrêt s'enregistre dans « Arrêts & IJ » (retour d'Elsa du 16/11) : le
  // calendrier ne le propose plus, sauf pour retyper un jour qui le porte déjà.
  if (currentType === 'arret_maladie') {
    options = [...options, { value: 'arret_maladie', label: 'Arrêt maladie' }];
  }
  if (activitePartielle || currentType === 'activite_partielle') {
    options = [...options, OPTION_ACTIVITE_PARTIELLE];
  }
  return options;
}

/** Types d'un jour dans un modèle de semaine (appliqué à des mois entiers) :
 * un jour travaillé ou non. Congés, RTT, arrêts et fériés sont des faits
 * datés, qui se posent au calendrier, pas dans un modèle (17/11 : le
 * dialogue proposait « Congé », sans effet sur la paie, et « Arrêt », retenu
 * sans maintien). Un type ancien porté par un modèle reste affiché. */
export function typesDUnModeleDeSemaine(currentType?: string | null): { value: string; label: string }[] {
  const options = CALENDAR_EDITABLE_TYPE_OPTIONS.filter((o) =>
    ['travail', 'weekend', 'repos'].includes(o.value),
  );
  if (currentType && !options.some((o) => o.value === currentType)) {
    return [...options, { value: currentType, label: getCalendarTypeLabel(currentType) }];
  }
  return options;
}

export function getCalendarTypeLabel(type: string | null | undefined): string {
  if (!type) return 'Week-end';
  return CALENDAR_TYPE_LABELS[type] ?? type;
}

export function formatCalendarValue(
  value: number | null | undefined,
  isForfaitJour: boolean
): string {
  if (value === null || value === undefined) return '–';
  if (isForfaitJour) {
    return value === 1 ? 'Oui (journée)' : 'Non';
  }
  return `${value.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} h`;
}

/** Le réel d'un jour quand la RH change son type (Lyon, 17/11/2026).
 *
 * Un type de jour non travaillé (congé, repos, férié, activité partielle…)
 * remet le réel à 0 (« Non » au forfait jours) : les heures faites gardées
 * d'avant comptaient comme travaillées, et un jour chômé d'activité partielle
 * avec 7 h faites ne chômait rien. Le réel saisi en même temps l'emporte : une
 * demi-journée reste possible, la RH saisit ensuite les heures faites.
 * « Travail » garde le réel, sauf en revenant d'un type non travaillé : réel
 * à saisir (null). « École » garde ses heures. `undefined` : ne pas toucher au réel. */
export function reelApresChangementDeType(
  nouveauType: string | null | undefined,
  ancienType: string | null | undefined,
  reelSaisi?: number | null,
): number | null | undefined {
  if (reelSaisi !== undefined) return reelSaisi;
  if (!nouveauType || nouveauType === ancienType) return undefined;
  // Retour à « Travail » depuis un type non travaillé : le 0 posé
  // automatiquement ferait du jour une absence ; le réel redevient à saisir.
  if (nouveauType === 'travail') return ancienType && ancienType !== 'travail' ? null : undefined;
  // École (CFA) : temps de travail effectif, ses heures restent (F2918).
  if (nouveauType === 'ecole') return undefined;
  return 0;
}

/** Types qu'une saisie d'heures sans type peut faire « Travail » : un jour
 * travaillé, un week-end, un repos, ou un jour sans type. */
const TYPES_REPRIS_PAR_DES_HEURES = new Set(['travail', 'weekend', 'repos', '']);

/** Saisie groupée d'heures sans type de jour (A5, 18/11) : un congé, un férié,
 * un jour d'école, un arrêt… de la sélection n'est pas touché. Avant, il
 * repassait en « Travail » et perdait son type sans le dire. Le jour
 * d'activité partielle garde sa propre règle (heures gardées, jour chômé). */
export function saisieGroupeeLaisseLeJour<T extends { type?: string | null; type_par_defaut?: string }>(
  saisie: T,
  ancienType: string | null | undefined,
): boolean {
  if (saisie.type != null || !saisie.type_par_defaut) return false;
  if (ancienType == null || ancienType === 'activite_partielle') return false;
  return !TYPES_REPRIS_PAR_DES_HEURES.has(ancienType);
}

/** Saisie groupée appliquée à un jour : même règle du réel que la case du jour.
 * Le panneau ne connaît pas l'ancien type de chaque jour ; ici on l'a :
 * - un jour repassé en « Travail » depuis un congé ou une activité partielle
 *   voit son réel redevenir à saisir, au lieu de garder le 0 qui en faisait
 *   une absence ;
 * - réappliquer le même type ne touche pas au réel (demi-journée gardée) ;
 * - des heures saisies sans type font un jour « Travail » (`type_par_defaut`),
 *   sauf un jour d'activité partielle : ses heures faites sont la part
 *   travaillée de la demi-journée, le jour reste chômé ; un congé, un férié,
 *   un jour d'école n'y arrivent pas (`saisieGroupeeLaisseLeJour`). */
export function saisieGroupeeDuJour<
  T extends { type?: string | null; heures_faites?: number | null; type_par_defaut?: string },
>(saisie: T, ancienType: string | null | undefined): Omit<T, 'type_par_defaut'> {
  const { type_par_defaut, ...reste } = saisie;
  let jour = reste as Omit<T, 'type_par_defaut'> & { type?: string | null; heures_faites?: number | null };
  if (jour.type == null && type_par_defaut && ancienType !== 'activite_partielle') {
    jour = { ...jour, type: type_par_defaut };
  }
  if (jour.type == null || jour.heures_faites !== undefined) return jour;
  const reel = reelApresChangementDeType(jour.type, ancienType);
  return reel === undefined ? jour : { ...jour, heures_faites: reel };
}

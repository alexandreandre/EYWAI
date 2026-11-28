/**
 * Primes liées aux pointages, dites dans les mots de la paie (examen
 * d'ergonomie du 20/11/2026) : « panier si le poste commence à 4 h ou à 12 h »
 * se tape « 4 » et « 12 », pas « 03:00 - 05:00 » ; les modèles préremplissent
 * le type, les exclusions et le réglage ; un montant oublié ou un libellé déjà
 * pris sont refusés au lieu de donner une prime fausse sans le dire.
 */
import type { PayrollVariableGenerateResult, PayrollVariablePreviewItem, PayrollVariableRule } from '@/api/payrollVariables';

export type PlageDebut = { de: string; a: string };

/** Marge autour de l'heure de début annoncée : un poste de 4 h badgé à 3 h 10 ou à 4 h 52 compte. */
export const MARGE_MINUTES = 60;

function enMinutes(texte: string): number | null {
  const t = texte.trim().toLowerCase().replace(/\s+/g, '');
  const m = /^(\d{1,2})(?:[h:](\d{2})?)?$/.exec(t);
  if (!m) return null;
  const h = Number(m[1]);
  const min = m[2] ? Number(m[2]) : 0;
  if (h > 23 || min > 59) return null;
  return h * 60 + min;
}

function enHeure(minutes: number): string {
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

/** « 4 », « 4h », « 12h30 », « 04:00 » → la plage d'une heure de chaque côté (bornée à la journée). */
export function plageAutourDe(texte: string): PlageDebut | null {
  const m = enMinutes(texte);
  if (m == null) return null;
  return { de: enHeure(Math.max(0, m - MARGE_MINUTES)), a: enHeure(Math.min(23 * 60 + 59, m + MARGE_MINUTES)) };
}

/** « vers 4 h » quand la plage est centrée sur une heure, sinon « de 03:30 à 04:30 ». */
export function direPlage(p: PlageDebut): string {
  const de = enMinutes(p.de);
  const a = enMinutes(p.a);
  if (de != null && a != null && a - de === 2 * MARGE_MINUTES) {
    const centre = de + MARGE_MINUTES;
    const h = Math.floor(centre / 60);
    const min = centre % 60;
    return `vers ${h} h${min ? ` ${String(min).padStart(2, '0')}` : ''}`;
  }
  return `de ${p.de} à ${p.a}`;
}

/** Population qui pointe (Elsa, 17/11) : cochée d'office sur une nouvelle prime de pointage. */
export const EXCLUSIONS_POINTAGE = {
  exclure_forfait_jours: true,
  exclure_cadres: true,
  exclure_alternants: true,
} as const;

export const TYPES_POINTAGE = new Set(['per_worked_day', 'per_week_without_absence', 'per_night_hour']);

export type ModelePrime = {
  id: string;
  titre: string;
  aide: string;
  regle: Partial<PayrollVariableRule>;
};

/** Les quatre besoins de la page d'Elsa, prêts à compléter (libellé, montant, heures). */
export const MODELES_PRIMES_POINTAGE: ModelePrime[] = [
  {
    id: 'panier',
    titre: 'Panier ou prime selon l’heure d’arrivée',
    aide: 'Par jour pointé, si le poste commence vers les heures indiquées (ex. 4 h et 12 h).',
    regle: {
      label: 'Panier',
      rule_type: 'per_worked_day',
      amount: null,
      conditions: { ...EXCLUSIONS_POINTAGE },
    },
  },
  {
    id: 'pause',
    titre: 'Pause payée en heures',
    aide: 'Par jour pointé, des heures au taux horaire de base (ex. 0,5 h).',
    regle: {
      label: 'Pause payée',
      rule_type: 'per_worked_day',
      amount: null,
      conditions: { ...EXCLUSIONS_POINTAGE, heures_par_jour: 0.5 },
    },
  },
  {
    id: 'assiduite',
    titre: 'Prime d’assiduité',
    aide: 'Au mois ou à la semaine sans absence, lue au calendrier.',
    regle: {
      label: 'Prime d’assiduité',
      rule_type: 'per_week_without_absence',
      amount: null,
      conditions: { ...EXCLUSIONS_POINTAGE, periode_assiduite: 'mois', absence_types: [] },
    },
  },
  {
    id: 'nuit',
    titre: 'Heures de nuit majorées',
    aide: 'Heures pointées entre 22 h et 6 h, majorées d’un pourcentage du taux horaire (ex. 50 %).',
    regle: {
      label: 'Heures de nuit',
      rule_type: 'per_night_hour',
      amount: null,
      conditions: { ...EXCLUSIONS_POINTAGE, depuis_les_pointages: true, majoration_pct: 50 },
    },
  },
];

/** Pourquoi le montant de la règle ne compte pas (heures au taux horaire, majoration en %), sinon null. */
export function montantIgnore(regle: Partial<PayrollVariableRule>): string | null {
  const c = (regle.conditions ?? {}) as Record<string, unknown>;
  // Le moteur ne lit les heures et la majoration que si elles valent plus que 0.
  if (regle.rule_type === 'per_worked_day' && Number(c.heures_par_jour) > 0) {
    return 'Inutile : les heures par jour sont payées au taux horaire de chaque salarié.';
  }
  if (regle.rule_type === 'per_night_hour' && Number(c.majoration_pct) > 0) {
    return 'Inutile : la majoration en % s’applique au taux horaire de chaque salarié.';
  }
  return null;
}

const SANS_MONTANT_SAISI = new Set([
  'per_astreinte_weekend_km',
  'per_astreinte_week_tiered',
  'per_astreinte_weekend_majoration',
  'transport_domicile_travail',
]);

/** Ce qui empêche d'enregistrer la règle, dit en clair ; null si elle est bonne. */
export function erreurDeLaRegle(
  regle: Partial<PayrollVariableRule>,
  regles: PayrollVariableRule[],
  idEnModification: string | null | undefined,
): string | null {
  const libelle = (regle.label ?? '').trim();
  if (!libelle) return 'Donnez un libellé à la prime (il s’imprime sur le bulletin).';
  const memeLibelle = (r: PayrollVariableRule) => (r.label ?? '').trim().toLowerCase() === libelle.toLowerCase();
  // Une règle qu'on modifie sans changer son libellé passe, même si une ancienne porte le même.
  const original = regles.find((r) => r.id === idEnModification);
  const pris = !(original && memeLibelle(original)) && regles.some((r) => r.id !== idEnModification && memeLibelle(r));
  if (pris) return `Une règle s’appelle déjà « ${libelle} » : choisissez un autre libellé, ou modifiez celle-là.`;
  const typeAvecMontant = !SANS_MONTANT_SAISI.has(regle.rule_type ?? '');
  // Montant non nul (une retenue fixe est négative), ou un taux.
  const montantDonne = (regle.amount != null && Number(regle.amount) !== 0) || regle.rate != null;
  if (typeAvecMontant && !montantIgnore(regle) && !montantDonne) {
    return 'Indiquez le montant de la prime.';
  }
  return null;
}

function jourMois(iso: string): string {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
}

/**
 * Les jours travaillés sans heure d'arrivée que la semaine ne tranche pas (ou
 * hors du prévu) : non comptés, dits avec leurs dates (L19, 26/11).
 */
export function phraseJoursSansHeureDArrivee(nombre: number, dates?: string[]): string {
  const jours = nombre > 1 ? 'jours travaillés' : 'jour travaillé';
  const comptes = nombre > 1 ? 'non comptés' : 'non compté';
  const liste = dates && dates.length ? ` (${dates.map(jourMois).join(', ')})` : '';
  return `${nombre} ${jours} sans heure d'arrivée, ${comptes}${liste} : heure d'arrivée à saisir au calendrier, ou absence à poser`;
}

/**
 * L'encadré de Primes du mois, par salarié et par groupe de jours identiques :
 * les règles concernées nommées ensemble, la liste des dates quand une partie
 * des jours a une heure d'arrivée ; une seule phrase quand aucun n'en a (aucun
 * badge importé). Mot pour mot l'alerte du bulletin (`alertes_paniers`, L23).
 */
export function phraseJoursDuSalarie(j: {
  rule_label?: string | null;
  rule_labels?: string[] | null;
  dates: string[];
  aucun_badge?: boolean;
}): string {
  const noms = j.rule_labels && j.rule_labels.length ? j.rule_labels : [j.rule_label ?? 'Prime'];
  const regles = noms.join(', ');
  const n = j.dates.length;
  const jours = n > 1 ? 'jours travaillés' : 'jour travaillé';
  if (j.aucun_badge) {
    const rien = noms.every((r) => /panier/i.test(r)) ? 'aucun panier compté' : 'aucun jour compté';
    return `${regles} : aucune heure d'arrivée sur la période (${n} ${jours}), ${rien} : importez les pointages, saisissez les heures d'arrivée au calendrier ou posez les absences.`;
  }
  const cesJours = n > 1 ? 'ces jours-là' : 'ce jour-là';
  return `${regles} : ${n} ${jours} sans heure d'arrivée (${j.dates.map(jourMois).join(', ')}) : aucun compté ${cesJours}. Importez les pointages, saisissez l'heure d'arrivée au calendrier ou posez l'absence.`;
}

/** Une ligne de simulation qui demande l'attention de la RH (prime à 0, jours sans heure d'arrivée). */
export function estUneAlerte(item: PayrollVariablePreviewItem): boolean {
  const d = item.details;
  return Boolean(d && (d.skip_reason || d.jours_sans_heure_de_debut));
}

/** Les alertes d'abord (toutes), puis les autres lignes. */
export function trierLaSimulation(result: PayrollVariableGenerateResult): {
  alertes: PayrollVariablePreviewItem[];
  lignes: PayrollVariablePreviewItem[];
} {
  return {
    alertes: result.preview.filter(estUneAlerte),
    lignes: result.preview.filter((p) => !estUneAlerte(p)),
  };
}

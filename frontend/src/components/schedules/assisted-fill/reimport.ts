/**
 * « Refaire l'import de ce fichier » : ce que l'écran dit d'un fichier déjà
 * importé, des jours corrigés à la main depuis, et de ce qui sera écrit.
 *
 * Le serveur refuse un fichier déjà importé (409 `deja_importe`) avec le lot
 * précédent ; la relecture porte les jours corrigés à la main depuis, que
 * l'enregistrement ne réécrit pas (la valeur du calendrier reste). Rien ne doit
 * laisser croire qu'une correction sera écrasée en silence.
 */
import type {
  CorrectionALaMain,
  LotPrecedent,
  RefusDejaImporte,
  ValeurJourImport,
} from '@/api/calendar';

/** Un jour d'un salarié, à sa date. */
interface JourCible {
  employee_id: string;
  annee: number;
  mois: number;
  jour: number;
}

/** Le corps du refus « déjà importé », ou null pour toute autre erreur. */
export function lireRefusDejaImporte(error: unknown): RefusDejaImporte | null {
  const detail = (error as { response?: { data?: { detail?: unknown } } } | null)?.response?.data
    ?.detail;
  if (
    detail &&
    typeof detail === 'object' &&
    (detail as { code?: unknown }).code === 'deja_importe' &&
    Array.isArray((detail as { fichiers?: unknown }).fichiers)
  ) {
    return detail as RefusDejaImporte;
  }
  return null;
}

const MOIS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

/** « le 1 octobre 2026 à 18:09 », à l'heure de Paris. */
function quand(iso: string): string | null {
  const instant = new Date(iso);
  if (Number.isNaN(instant.getTime())) return null;
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('fr-FR', {
      timeZone: 'Europe/Paris',
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    })
      .formatToParts(instant)
      .map((p) => [p.type, p.value]),
  );
  return `le ${Number(parts.day)} ${MOIS[Number(parts.month) - 1]} ${parts.year} à ${parts.hour}:${parts.minute}`;
}

function pluriel(n: number, singulier: string, plurielForme: string): string {
  return `${n} ${n > 1 ? plurielForme : singulier}`;
}

/** « importé le 1 octobre 2026 à 18:09 par RH Démo · 47 jours écrits ». */
export function libelleLotPrecedent(lot: LotPrecedent): string {
  const morceaux = ['importé'];
  const date = lot.valide_le ? quand(lot.valide_le) : null;
  if (date) morceaux.push(date);
  if (lot.valide_par) morceaux.push(`par ${lot.valide_par}`);
  let texte = morceaux.join(' ');
  if (lot.jours_ecrits != null) {
    texte += ` · ${pluriel(lot.jours_ecrits, 'jour écrit', 'jours écrits')}`;
  }
  return texte;
}

const TYPES: Record<string, string> = {
  arret_maladie: 'arrêt maladie',
  conge: 'congé payé',
  conges_payes: 'congé payé',
  rtt: 'RTT',
  repos: 'repos',
  weekend: 'repos',
  ferie: 'férié',
  absence: 'absence',
  ecole: 'école',
  travail: 'travail',
};

function heures(h: number): string {
  return `${h.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} h`;
}

/** « 8,5 h », « arrêt maladie », « vide ». */
export function libelleValeur(valeur: ValeurJourImport | null): string {
  if (!valeur) return 'vide';
  if (valeur.heures != null) return heures(valeur.heures);
  if (!valeur.type) return 'vide';
  return TYPES[valeur.type] ?? valeur.type.replace(/_/g, ' ');
}

/** « modifié à la main depuis l’import : 8,5 h → 9 h ». */
export function libelleCorrection(c: CorrectionALaMain): string {
  if (!c.import_precedent) {
    return `saisi à la main hors de l’import : ${libelleValeur(c.calendrier)}`;
  }
  const verbe = c.calendrier ? 'modifié' : 'effacé';
  return `${verbe} à la main depuis l’import : ${libelleValeur(c.import_precedent)} → ${libelleValeur(c.calendrier)}`;
}

export function cleJour(j: JourCible): string {
  return `${j.employee_id}|${j.annee}|${j.mois}|${j.jour}`;
}

export interface BilanReimport {
  joursEcrits: number;
  correctionsGardees: number;
}

/**
 * Ce que l'enregistrement fera : `joursEnvoyes` sont les clés des jours réels
 * qui partent (lignes enregistrables), `totalJours` tous les jours envoyés.
 * Une correction gardée n'est pas écrite.
 */
export function bilanReimport(
  joursEnvoyes: string[],
  totalJours: number,
  corrections: CorrectionALaMain[],
): BilanReimport {
  const envoyes = new Set(joursEnvoyes);
  const correctionsGardees = corrections.filter((c) => envoyes.has(cleJour(c))).length;
  return { joursEcrits: totalJours - correctionsGardees, correctionsGardees };
}

/**
 * Après l'enregistrement, d'après le résumé du lot (ce que le serveur a
 * vraiment fait, garde recalculée à l'enregistrement comprise).
 */
export function libelleImportRefait(
  summary:
    | {
        committed_days?: number | null;
        corrections_gardees?: CorrectionALaMain[] | null;
      }
    | null
    | undefined,
): string {
  const jours = summary?.committed_days ?? 0;
  const gardees = summary?.corrections_gardees?.length ?? 0;
  return [
    pluriel(jours, 'jour écrit', 'jours écrits'),
    gardees > 0
      ? pluriel(gardees, 'correction faite à la main gardée', 'corrections faites à la main gardées')
      : 'aucune correction faite à la main n’était à garder',
  ].join(' · ');
}

/** « 44 jours seront écrits · 3 corrections faites à la main gardées ». */
export function libelleBilan(bilan: BilanReimport): string {
  return [
    bilan.joursEcrits > 1
      ? `${bilan.joursEcrits} jours seront écrits`
      : `${bilan.joursEcrits} jour sera écrit`,
    bilan.correctionsGardees > 0
      ? pluriel(
          bilan.correctionsGardees,
          'correction faite à la main gardée',
          'corrections faites à la main gardées',
        )
      : 'aucune correction faite à la main à garder',
  ].join(' · ');
}

/**
 * Retraite progressive : réglage de la fiche, rangé dans
 * `specificites_paie.retraite_progressive` (lu par le moteur,
 * backend/app/modules/payroll/engine/retraite_progressive.py).
 *
 * - quotité : part du temps plein travaillée, 40 à 80 % (CSS R161-19-6) ;
 * - vieillesse sur un temps plein (CSS L241-3-1) : accord écrit de l'employeur ;
 * - complémentaire sur un temps plein (ANI Agirc-Arrco, art. 75) ;
 * - prise en charge par l'employeur de la part salariale du supplément
 *   (CSS R241-0-3, II) ; sans elle, chacun paie sa part. Sur la part
 *   complémentaire, la prise en charge paie le forfait social de 20 % (L137-15).
 *
 * Une case absente d'une fiche enregistrée vaut « non », comme pour le moteur ;
 * seul un réglage neuf part avec la vieillesse cochée.
 */

export interface RetraiteProgressiveFiche {
  actif?: boolean;
  quotite?: number | string | null;
  date_debut?: string | null;
  date_fin?: string | null;
  vieillesse_temps_plein?: boolean;
  complementaire_temps_plein?: boolean;
  prise_en_charge_part_salariale?: boolean;
  salaire_temps_plein?: number | string | null;
}

export interface RetraiteProgressiveForm {
  actif: boolean;
  quotite: string;
  date_debut: string;
  date_fin: string;
  vieillesse_temps_plein: boolean;
  complementaire_temps_plein: boolean;
  prise_en_charge_part_salariale: boolean;
  salaire_temps_plein: string;
}

export const RETRAITE_PROGRESSIVE_VIDE: RetraiteProgressiveForm = {
  actif: false,
  quotite: '',
  date_debut: '',
  date_fin: '',
  vieillesse_temps_plein: true,
  complementaire_temps_plein: false,
  prise_en_charge_part_salariale: false,
  salaire_temps_plein: '',
};

export const MESSAGE_QUOTITE = 'Une quotité entre 40 et 80 % du temps plein (ex. 50).';
export const MESSAGE_DATE_DEBUT = 'La date de début de la retraite progressive.';
export const MESSAGE_AUCUNE_COTISATION =
  'Cochez la vieillesse ou la retraite complémentaire sur un temps plein : sans elles, le bulletin ne change pas.';

/** Le formulaire est typé partiel par zod : les cases absentes prennent leur valeur vide. */
function complet(saisie: Partial<RetraiteProgressiveForm> | undefined): RetraiteProgressiveForm {
  return { ...RETRAITE_PROGRESSIVE_VIDE, ...(saisie ?? {}) };
}

function nombre(texte: string | undefined): number | null {
  const brut = (texte ?? '').trim().replace('%', '').replace(',', '.');
  if (!brut) return null;
  const valeur = Number(brut);
  return Number.isFinite(valeur) ? valeur : Number.NaN;
}

/** Quotité saisie en pourcentage, rendue en fraction ; null si vide, NaN si hors bornes. */
export function quotiteSaisie(texte: string | undefined): number | null {
  const valeur = nombre(texte);
  if (valeur === null) return null;
  if (Number.isNaN(valeur) || valeur < 40 || valeur > 80) return Number.NaN;
  return Math.round(valeur * 100) / 10000;
}

export function retraiteProgressiveDuFormulaire(fiche: unknown): RetraiteProgressiveForm {
  if (!fiche || typeof fiche !== 'object') return { ...RETRAITE_PROGRESSIVE_VIDE };
  const r = fiche as RetraiteProgressiveFiche;
  const quotite = r.quotite === null || r.quotite === undefined || r.quotite === '' ? null : Number(r.quotite);
  return {
    actif: Boolean(r.actif),
    quotite:
      quotite === null || !Number.isFinite(quotite)
        ? ''
        : String(Math.round((quotite <= 1 ? quotite * 100 : quotite) * 100) / 100),
    date_debut: (r.date_debut ?? '').slice(0, 10),
    date_fin: (r.date_fin ?? '').slice(0, 10),
    vieillesse_temps_plein: Boolean(r.vieillesse_temps_plein),
    complementaire_temps_plein: Boolean(r.complementaire_temps_plein),
    prise_en_charge_part_salariale: Boolean(r.prise_en_charge_part_salariale),
    salaire_temps_plein:
      r.salaire_temps_plein === null || r.salaire_temps_plein === undefined ? '' : String(r.salaire_temps_plein),
  };
}

/** Les erreurs du réglage, par champ ; vide quand tout est bon ou décoché. */
export function erreursRetraiteProgressive(
  saisie: Partial<RetraiteProgressiveForm> | undefined,
): Partial<Record<keyof RetraiteProgressiveForm, string>> {
  const form = complet(saisie);
  if (!form.actif) return {};
  const erreurs: Partial<Record<keyof RetraiteProgressiveForm, string>> = {};
  const quotite = quotiteSaisie(form.quotite);
  if (quotite === null || Number.isNaN(quotite)) erreurs.quotite = MESSAGE_QUOTITE;
  if (!form.date_debut) erreurs.date_debut = MESSAGE_DATE_DEBUT;
  if (!form.vieillesse_temps_plein && !form.complementaire_temps_plein) {
    erreurs.vieillesse_temps_plein = MESSAGE_AUCUNE_COTISATION;
  }
  if (form.date_fin && form.date_debut && form.date_fin < form.date_debut) {
    erreurs.date_fin = 'La date de fin ne peut pas précéder la date de début.';
  }
  const salaire = nombre(form.salaire_temps_plein);
  if (salaire !== null && (Number.isNaN(salaire) || salaire <= 0)) {
    erreurs.salaire_temps_plein = 'Un montant mensuel en euros, ou la case vide.';
  }
  return erreurs;
}

/**
 * Ce que l'enregistrement écrit : le réglage complet quand la case est cochée,
 * `actif: false` pour décocher un réglage existant, et rien sinon (une fiche
 * sans retraite progressive garde son empreinte « À recalculer »).
 */
export function retraiteProgressivePourEnvoi(
  saisie: Partial<RetraiteProgressiveForm> | undefined,
  existant: unknown,
): RetraiteProgressiveFiche | undefined {
  const form = complet(saisie);
  if (!form.actif) {
    return existant && typeof existant === 'object' ? { ...(existant as RetraiteProgressiveFiche), actif: false } : undefined;
  }
  const salaire = nombre(form.salaire_temps_plein);
  return {
    actif: true,
    quotite: quotiteSaisie(form.quotite),
    date_debut: form.date_debut || null,
    date_fin: form.date_fin || null,
    vieillesse_temps_plein: form.vieillesse_temps_plein,
    complementaire_temps_plein: form.complementaire_temps_plein,
    prise_en_charge_part_salariale: form.prise_en_charge_part_salariale,
    salaire_temps_plein: salaire === null || Number.isNaN(salaire) ? null : salaire,
  };
}

/** Jours du forfait attendus pour la quotité (218 jours à temps plein). */
export function joursAttendus(saisie: Partial<RetraiteProgressiveForm> | undefined): number | null {
  const quotite = quotiteSaisie(complet(saisie).quotite);
  return quotite === null || Number.isNaN(quotite) ? null : Math.round(quotite * 218);
}

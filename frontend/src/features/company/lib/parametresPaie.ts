/**
 * Réglages de paie de la société saisis dans la carte « Paramètres de paie » :
 * taux d'assurance chômage notifié (bonus-malus), effectif retenu pour les
 * seuils, date de paiement des salaires, journée de solidarité.
 *
 * Le moteur les lit déjà (backend : companies.effectif et companies.settings).
 * Le serveur valide aussi (app/modules/companies/domain/parametres_paie.py) ;
 * ici, on dit à la gestionnaire quoi corriger avant d'envoyer, et on n'envoie
 * que ce qui change : chaque réglage entre dans l'empreinte des bulletins, et
 * réécrire une valeur par défaut les ferait tous passer « À recalculer ».
 */

import type { CompanyDetails, CompanyDetailsUpdate, DatePaiement } from '@/api/company';

/** Bornes du bonus-malus depuis le 1er mai 2025 (taux de référence 4 %). */
export const TAUX_CHOMAGE_MIN = 2.95;
export const TAUX_CHOMAGE_MAX = 5;

/** Sans réglage, le moteur paie à la date de l'arrêté des variables. */
export const DATE_PAIEMENT_PAR_DEFAUT: DatePaiement = 'arrete_des_variables';

export const LIBELLES_DATE_PAIEMENT: Record<DatePaiement, string> = {
  dernier_jour_du_mois: 'Dernier jour du mois',
  arrete_des_variables: "Jour de l'arrêté des variables",
};

export const DESCRIPTIONS_DATE_PAIEMENT: Record<DatePaiement, string> = {
  dernier_jour_du_mois: 'Le bulletin indique un paiement le 30 ou le 31.',
  arrete_des_variables:
    "Le bulletin indique un paiement le jour de l'arrêté de la période de paie choisi ci-dessus.",
};

export interface SaisieParametresPaie {
  tauxChomage: string;
  effectif: string;
  datePaiement: DatePaiement;
  jourSolidarite: string;
}

export type ErreursParametresPaie = Partial<Record<keyof SaisieParametresPaie, string>>;

export type MiseAJourParametresPaie = Pick<
  CompanyDetailsUpdate,
  'effectif' | 'taux_assurance_chomage' | 'date_paiement' | 'jour_solidarite'
>;

const LIBELLES_CHAMPS: Record<keyof MiseAJourParametresPaie, string> = {
  effectif: 'Effectif retenu pour les seuils',
  taux_assurance_chomage: "Taux d'assurance chômage",
  date_paiement: 'Date de paiement des salaires',
  jour_solidarite: 'Journée de solidarité',
};

const ORDRE_CHAMPS: (keyof MiseAJourParametresPaie)[] = [
  'effectif',
  'taux_assurance_chomage',
  'date_paiement',
  'jour_solidarite',
];

function estDatePaiement(valeur: unknown): valeur is DatePaiement {
  return valeur === 'dernier_jour_du_mois' || valeur === 'arrete_des_variables';
}

/** Valeurs enregistrées, à plat ; `null` quand rien n'est réglé. */
function enregistres(company: CompanyDetails) {
  const reglages = company.settings ?? {};
  return {
    effectif: company.effectif ?? null,
    taux_assurance_chomage: reglages.taux_assurance_chomage ?? null,
    date_paiement: estDatePaiement(reglages.date_paiement) ? reglages.date_paiement : null,
    jour_solidarite: reglages.jour_solidarite ?? null,
  };
}

function memeValeur(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (a === null || a === undefined || b === null || b === undefined) {
    return (a ?? null) === (b ?? null);
  }
  if (typeof a === 'number' || typeof b === 'number') return Number(a) === Number(b);
  return false;
}

export function saisieInitiale(company: CompanyDetails): SaisieParametresPaie {
  const valeurs = enregistres(company);
  return {
    tauxChomage: valeurs.taux_assurance_chomage != null ? String(valeurs.taux_assurance_chomage) : '',
    effectif: valeurs.effectif != null ? String(valeurs.effectif) : '',
    datePaiement: valeurs.date_paiement ?? DATE_PAIEMENT_PAR_DEFAUT,
    jourSolidarite: valeurs.jour_solidarite ?? '',
  };
}

/** Date AAAA-MM-JJ qui existe au calendrier, sinon null. */
function lireDate(saisie: string): { annee: number; mois: number; jour: number } | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(saisie.trim());
  if (!m) return null;
  const [annee, mois, jour] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const d = new Date(Date.UTC(annee, mois - 1, jour));
  if (d.getUTCFullYear() !== annee || d.getUTCMonth() !== mois - 1 || d.getUTCDate() !== jour) {
    return null;
  }
  return { annee, mois, jour };
}

/**
 * Corps du PATCH (seulement les réglages qui changent) et erreurs à afficher
 * sous chaque champ. Avec une erreur, le champ fautif n'est pas envoyé.
 */
export function construireMiseAJour(
  company: CompanyDetails,
  saisie: SaisieParametresPaie,
): { corps: MiseAJourParametresPaie; erreurs: ErreursParametresPaie } {
  const avant = enregistres(company);
  const corps: MiseAJourParametresPaie = {};
  const erreurs: ErreursParametresPaie = {};

  const taux = saisie.tauxChomage.trim().replace(',', '.');
  if (taux === '') {
    if (avant.taux_assurance_chomage != null) corps.taux_assurance_chomage = null;
  } else if (!/^-?\d+(\.\d+)?$/.test(taux)) {
    erreurs.tauxChomage = 'Indiquez un nombre, par exemple 4,05.';
  } else {
    const valeur = Number(taux);
    if (valeur < TAUX_CHOMAGE_MIN || valeur > TAUX_CHOMAGE_MAX) {
      erreurs.tauxChomage =
        'Le taux notifié est compris entre 2,95 % et 5 %. Laissez vide pour le taux normal.';
    } else if (!memeValeur(avant.taux_assurance_chomage, valeur)) {
      corps.taux_assurance_chomage = valeur;
    }
  }

  const effectif = saisie.effectif.trim();
  if (effectif === '') {
    if (avant.effectif != null) {
      erreurs.effectif =
        "L'effectif ne peut pas rester vide : indiquez un nombre entier, 0 ou plus.";
    }
  } else if (!/^\d+$/.test(effectif)) {
    erreurs.effectif = 'Indiquez un nombre entier, 0 ou plus.';
  } else if (!memeValeur(avant.effectif, Number(effectif))) {
    corps.effectif = Number(effectif);
  }

  if (saisie.datePaiement !== (avant.date_paiement ?? DATE_PAIEMENT_PAR_DEFAUT)) {
    corps.date_paiement = saisie.datePaiement;
  }

  const jour = saisie.jourSolidarite.trim();
  if (jour === '') {
    if (avant.jour_solidarite != null) corps.jour_solidarite = null;
  } else if (!lireDate(jour)) {
    erreurs.jourSolidarite = 'Date invalide : choisissez un jour du calendrier.';
  } else if (jour !== avant.jour_solidarite) {
    corps.jour_solidarite = jour;
  }

  return { corps, erreurs };
}

/** La date réglée sert une seule année : on prévient quand elle a vieilli. */
export function avertissementJourSolidarite(saisie: string, anneeCourante: number): string | null {
  const date = lireDate(saisie);
  if (!date || date.annee === anneeCourante) return null;
  return `Cette date est en ${date.annee} : indiquez celle de ${anneeCourante}.`;
}

/** Libellés des réglages envoyés que la société relue ne porte pas. */
export function champsNonRelus(corps: MiseAJourParametresPaie, relue: CompanyDetails): string[] {
  const apres = enregistres(relue);
  return ORDRE_CHAMPS.filter(
    (champ) => champ in corps && !memeValeur(corps[champ] ?? null, apres[champ]),
  ).map((champ) => LIBELLES_CHAMPS[champ]);
}

/** Un réglage qui entre dans le calcul a-t-il changé entre deux lectures ? */
export function parametresOntChange(avant: CompanyDetails, apres: CompanyDetails): boolean {
  const a = enregistres(avant);
  const b = enregistres(apres);
  return (
    ORDRE_CHAMPS.some((champ) => !memeValeur(a[champ], b[champ])) ||
    !memeValeur(avant.taux_at_mp, apres.taux_at_mp) ||
    !memeValeur(avant.paie_jour_de_fin, apres.paie_jour_de_fin) ||
    !memeValeur(avant.paie_occurrence, apres.paie_occurrence)
  );
}

/** Une ligne lisible de ce qui s'applique, pour confirmer l'enregistrement. */
export function resumeParametresPaie(company: CompanyDetails): string {
  const v = enregistres(company);
  const effectif = v.effectif != null ? `Effectif ${v.effectif}` : 'Effectif non renseigné';
  const chomage =
    v.taux_assurance_chomage != null
      ? `chômage ${String(v.taux_assurance_chomage).replace('.', ',')} %`
      : 'chômage au taux normal';
  const paiement = `paiement le ${LIBELLES_DATE_PAIEMENT[
    v.date_paiement ?? DATE_PAIEMENT_PAR_DEFAUT
  ].toLowerCase()}`;
  const date = v.jour_solidarite ? lireDate(v.jour_solidarite) : null;
  const solidarite = date
    ? `solidarité le ${String(date.jour).padStart(2, '0')}/${String(date.mois).padStart(2, '0')}/${date.annee}`
    : 'solidarité le lundi de Pentecôte';
  return [effectif, chomage, paiement, solidarite].join(' · ');
}

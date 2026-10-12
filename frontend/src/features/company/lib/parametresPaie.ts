/**
 * Réglages de paie de la société saisis dans la carte « Paramètres de paie » :
 * taux d'assurance chômage notifié (bonus-malus), effectif retenu pour les
 * seuils, date de paiement des salaires, journée de solidarité.
 *
 * Le moteur les lit dans companies.settings. L'effectif s'y range par année
 * (`effectif_seuils`) : la colonne companies.effectif n'est que le nombre de
 * comptes de la société, que tient un déclencheur de la base.
 * Le serveur valide aussi (app/modules/companies/domain/parametres_paie.py) ;
 * ici, on dit à la gestionnaire quoi corriger avant d'envoyer, et on n'envoie
 * que ce qui change : chaque réglage entre dans l'empreinte des bulletins, et
 * réécrire une valeur par défaut les ferait tous passer « À recalculer ».
 */

import type {
  CompanyDetails,
  CompanyDetailsUpdate,
  CompteBancaireSociete,
  DatePaiement,
} from '@/api/company';
import { ibanProblem, normalizeIban } from '@/lib/iban';

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
  /** Compte qui débite les salaires (donneur d'ordre des remises SEPA). */
  compteIban: string;
  compteBic: string;
  compteTitulaire: string;
}

export type ErreursParametresPaie = Partial<Record<keyof SaisieParametresPaie, string>>;

export type MiseAJourParametresPaie = Pick<
  CompanyDetailsUpdate,
  | 'effectif'
  | 'effectif_annee'
  | 'taux_assurance_chomage'
  | 'date_paiement'
  | 'jour_solidarite'
  | 'compte_bancaire'
>;

/** L'année dont la carte saisit l'effectif. */
export function anneeEnCours(): number {
  return new Date().getFullYear();
}

/** Les effectifs saisis, par année ; les valeurs illisibles sont ignorées. */
function effectifsSaisis(company: CompanyDetails): Map<number, number> {
  const saisis = new Map<number, number>();
  const brut = company.settings?.effectif_seuils;
  if (!brut || typeof brut !== 'object') return saisis;
  for (const [annee, valeur] of Object.entries(brut)) {
    if (/^\d{4}$/.test(annee) && Number.isInteger(valeur) && valeur >= 0) {
      saisis.set(Number(annee), valeur);
    }
  }
  return saisis;
}

const LIBELLES_CHAMPS: Record<Exclude<keyof MiseAJourParametresPaie, 'effectif_annee'>, string> = {
  effectif: 'Effectif retenu pour les seuils',
  taux_assurance_chomage: "Taux d'assurance chômage",
  date_paiement: 'Date de paiement des salaires',
  jour_solidarite: 'Journée de solidarité',
  compte_bancaire: 'Compte bancaire de la société',
};

/** Les réglages qui entrent dans le calcul des bulletins. */
const CHAMPS_DU_CALCUL = [
  'effectif',
  'taux_assurance_chomage',
  'date_paiement',
  'jour_solidarite',
] as const;

/** Tous les réglages de la carte ; le compte bancaire ne touche à aucun bulletin. */
const ORDRE_CHAMPS: (keyof typeof LIBELLES_CHAMPS)[] = [...CHAMPS_DU_CALCUL, 'compte_bancaire'];

const BIC = /^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$/;

function estDatePaiement(valeur: unknown): valeur is DatePaiement {
  return valeur === 'dernier_jour_du_mois' || valeur === 'arrete_des_variables';
}

/** Valeurs enregistrées, à plat ; `null` quand rien n'est réglé. */
function enregistres(company: CompanyDetails, annee: number) {
  const reglages = company.settings ?? {};
  return {
    effectif: effectifsSaisis(company).get(annee) ?? null,
    taux_assurance_chomage: reglages.taux_assurance_chomage ?? null,
    date_paiement: estDatePaiement(reglages.date_paiement) ? reglages.date_paiement : null,
    jour_solidarite: reglages.jour_solidarite ?? null,
    compte_bancaire: compteNormalise(reglages.compte_bancaire),
  };
}

/** Compte enregistré, IBAN et BIC sans espaces ; null quand il n'y a pas d'IBAN. */
function compteNormalise(
  compte: CompteBancaireSociete | null | undefined,
): Required<CompteBancaireSociete> | null {
  const iban = normalizeIban(compte?.iban ?? '');
  if (!iban) return null;
  return {
    iban,
    bic: (compte?.bic ?? '').replace(/[\s-]/g, '').toUpperCase(),
    titulaire: (compte?.titulaire ?? '').trim(),
  };
}

function memeValeur(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a === 'object' && a !== null && typeof b === 'object' && b !== null) {
    return JSON.stringify(a) === JSON.stringify(b);
  }
  if (a === null || a === undefined || b === null || b === undefined) {
    return (a ?? null) === (b ?? null);
  }
  if (typeof a === 'number' || typeof b === 'number') return Number(a) === Number(b);
  return false;
}

export function saisieInitiale(
  company: CompanyDetails,
  annee: number = anneeEnCours(),
): SaisieParametresPaie {
  const valeurs = enregistres(company, annee);
  return {
    tauxChomage: valeurs.taux_assurance_chomage != null ? String(valeurs.taux_assurance_chomage) : '',
    effectif: valeurs.effectif != null ? String(valeurs.effectif) : '',
    datePaiement: valeurs.date_paiement ?? DATE_PAIEMENT_PAR_DEFAUT,
    jourSolidarite: valeurs.jour_solidarite ?? '',
    compteIban: valeurs.compte_bancaire?.iban ?? '',
    compteBic: valeurs.compte_bancaire?.bic ?? '',
    compteTitulaire: valeurs.compte_bancaire?.titulaire ?? '',
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
  annee: number = anneeEnCours(),
): { corps: MiseAJourParametresPaie; erreurs: ErreursParametresPaie } {
  const avant = enregistres(company, annee);
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
    corps.effectif_annee = annee;
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

  const compteIban = normalizeIban(saisie.compteIban);
  const compteBic = saisie.compteBic.replace(/[\s-]/g, '').toUpperCase();
  const compteTitulaire = saisie.compteTitulaire.trim();
  if (!compteIban && !compteBic && !compteTitulaire) {
    if (avant.compte_bancaire != null) corps.compte_bancaire = null;
  } else {
    const problemeIban = compteIban
      ? ibanProblem(compteIban)
      : "L'IBAN du compte est obligatoire. Pour retirer le compte, videz aussi le BIC et le titulaire.";
    if (problemeIban) erreurs.compteIban = problemeIban;
    if (compteBic && !BIC.test(compteBic)) {
      erreurs.compteBic = 'BIC invalide : 8 ou 11 caractères, par exemple BNPAFRPP.';
    }
    if (compteTitulaire.length > 70) {
      erreurs.compteTitulaire = 'Le titulaire tient en 70 caractères au plus (limite du fichier SEPA).';
    }
    if (!problemeIban && !erreurs.compteBic && !erreurs.compteTitulaire) {
      const compte = { iban: compteIban, bic: compteBic, titulaire: compteTitulaire };
      if (!memeValeur(avant.compte_bancaire, compte)) corps.compte_bancaire = compte;
    }
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
  const apres = enregistres(relue, corps.effectif_annee ?? anneeEnCours());
  return ORDRE_CHAMPS.filter(
    (champ) => champ in corps && !memeValeur(corps[champ] ?? null, apres[champ]),
  ).map((champ) => LIBELLES_CHAMPS[champ]);
}

/** Un réglage qui entre dans le calcul a-t-il changé entre deux lectures ? */
export function parametresOntChange(avant: CompanyDetails, apres: CompanyDetails): boolean {
  const a = enregistres(avant, anneeEnCours());
  const b = enregistres(apres, anneeEnCours());
  const effectifs = (c: CompanyDetails) => JSON.stringify([...effectifsSaisis(c)].sort());
  return (
    CHAMPS_DU_CALCUL.some((champ) => !memeValeur(a[champ], b[champ])) ||
    effectifs(avant) !== effectifs(apres) ||
    !memeValeur(avant.taux_at_mp, apres.taux_at_mp) ||
    !memeValeur(avant.paie_jour_de_fin, apres.paie_jour_de_fin) ||
    !memeValeur(avant.paie_occurrence, apres.paie_occurrence)
  );
}

/** Phrase ajoutée quand un réglage du calcul a changé : vraie pour les brouillons seulement. */
export const PHRASE_A_RECALCULER =
  'Les brouillons déjà calculés passent « À recalculer » ; un bulletin validé n’est pas touché.';

/**
 * Le message qui suit « Enregistrer » ([B10], 12/10/2026). Le serveur n'écrit
 * rien quand rien ne change, et l'écran affichait quand même « Paramètres paie
 * enregistrés ». Un bulletin validé ignore les réglages de la société : seuls
 * les brouillons passent « À recalculer ».
 */
export function messageApresEnregistrement(
  avant: CompanyDetails,
  relue: CompanyDetails,
): { titre: string; description: string } {
  const resume = `${resumeParametresPaie(relue)}.`;
  if (parametresOntChange(avant, relue)) {
    return { titre: 'Paramètres paie enregistrés', description: `${resume} ${PHRASE_A_RECALCULER}` };
  }
  const compteAvant = enregistres(avant, anneeEnCours()).compte_bancaire;
  const compteApres = enregistres(relue, anneeEnCours()).compte_bancaire;
  if (!memeValeur(compteAvant, compteApres)) {
    return { titre: 'Paramètres paie enregistrés', description: resume };
  }
  return { titre: 'Aucun changement à enregistrer', description: `Les réglages restent : ${resume}` };
}

/** Une ligne lisible de ce qui s'applique, pour confirmer l'enregistrement. */
export function resumeParametresPaie(
  company: CompanyDetails,
  annee: number = anneeEnCours(),
): string {
  const v = enregistres(company, annee);
  const effectif =
    v.effectif != null ? `Effectif ${annee} : ${v.effectif}` : `Effectif ${annee} non saisi`;
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

/**
 * Ce que Martine retient quand l'effectif de l'année n'est pas saisi (même
 * règle que le serveur : la dernière année saisie avant, sinon la plus proche
 * après, sinon le nombre de comptes) ; null quand l'année est saisie.
 */
export function repliEffectif(company: CompanyDetails, annee: number = anneeEnCours()): string | null {
  const saisis = effectifsSaisis(company);
  if (saisis.has(annee)) return null;
  const annees = [...saisis.keys()];
  const avant = annees.filter((a) => a < annee);
  const apres = annees.filter((a) => a > annee);
  const source = avant.length ? Math.max(...avant) : apres.length ? Math.min(...apres) : null;
  if (source !== null) {
    return `Non saisi pour ${annee} : Martine reprend celui de ${source} (${saisis.get(source)}).`;
  }
  return `Non saisi pour ${annee} : Martine compte les comptes de la société (${company.effectif ?? 0}), qui ne sont pas l'effectif légal.`;
}

/**
 * Heures de récupération du bulletin (spec 2026-11-05-heures-de-recuperation) :
 * ce que la carte du bulletin lit et dit.
 */

export interface EtatRecuperation {
  /** Heures sup du mois (fenêtre des variables). */
  heuresSupDuMois: number;
  /** Heures sup mises au compteur ce mois-ci. */
  heuresSupAuCompteur: number;
  /** Heures de repos créditées (équivalent majoré). */
  reposCredite: number;
  /** La RH a choisi de payer les heures sup de ce mois. */
  payeesCeMois: boolean;
  /** Solde du compteur à la fin du mois. */
  solde: number;
  /** Heures du compteur payées sur ce bulletin. */
  soldePaye: number;
}

/** BOSS (heures supplémentaires) et BOFiP BOI-RSA-CHAMP-20-50-20-40. */
export const CONSEQUENCE_DU_CHOIX =
  "Payées ce mois-ci, ces heures gardent l'exonération d'impôt et les réductions " +
  'des heures sup. Mises au compteur puis payées plus tard (solde de janvier, départ), ' +
  'elles les perdent : mieux vaut payer tout de suite les heures qui ne seront pas prises en repos.';

const nombre = (v: unknown): number => {
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
};

export function heuresFr(h: number): string {
  const arrondi = Math.round(h * 100) / 100;
  return `${String(arrondi).replace('.', ',')} h`;
}

/** Null quand la société paie ses heures sup (le bulletin n'a pas de compteur). */
export function lireRecuperation(payslipData: unknown): EtatRecuperation | null {
  if (!payslipData || typeof payslipData !== 'object') return null;
  const objet = (v: unknown): Record<string, unknown> | null =>
    v && typeof v === 'object' ? (v as Record<string, unknown>) : null;
  const data = objet(payslipData);
  const recup = objet(objet(objet(data?.pied_de_page)?.solde_conges)?.recuperation);
  if (!data || !recup) return null;
  const mod = (data.modulation_account ?? {}) as Record<string, unknown>;
  return {
    heuresSupDuMois: nombre(mod.hs_realisees),
    heuresSupAuCompteur: nombre(mod.hs_credited),
    reposCredite: nombre(mod.repos_credite),
    payeesCeMois: mod.paye_ce_mois === true,
    solde: nombre(recup.solde),
    soldePaye: nombre(recup.paye),
  };
}

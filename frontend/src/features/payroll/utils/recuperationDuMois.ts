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
  /** Ce qui se paie comme un solde (sans le crédit de ce mois). */
  soldePayable: number;
  /** La règle de la société : au compteur, ou payées (avec un compteur suivi). */
  regle: 'compteur' | 'payees' | 'autre';
  /** La RH a choisi de mettre au compteur les heures de ce mois (société qui paie). */
  auCompteurCeMois: boolean;
}

/** BOSS (heures supplémentaires) et BOFiP BOI-RSA-CHAMP-20-50-20-40. */
export const CONSEQUENCE_DU_CHOIX =
  "Payées ce mois-ci, ces heures gardent l'exonération d'impôt et les réductions " +
  'des heures sup. Mises au compteur puis payées plus tard (solde de janvier, départ), ' +
  'elles les perdent : mieux vaut payer tout de suite les heures qui ne seront pas prises en repos.';

/** Sans accord collectif : C. trav. L3121-37. */
export const CONDITIONS_DU_COMPTEUR =
  'Sans accord collectif, la loi permet le repos à la place du paiement si la société n’a pas ' +
  'de délégué syndical et si le CSE, quand il existe, ne s’y oppose pas (Code du travail, L3121-37).';

const nombre = (v: unknown): number => {
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
};

export function heuresFr(h: number): string {
  const arrondi = Math.round(h * 100) / 100;
  return `${String(arrondi).replace('.', ',')} h`;
}

/** Null quand rien n'est à dire : compteur fermé, ou salarié sans compteur et sans heures sup. */
export function lireRecuperation(payslipData: unknown): EtatRecuperation | null {
  const objet = (v: unknown): Record<string, unknown> | null =>
    v && typeof v === 'object' ? (v as Record<string, unknown>) : null;
  const data = objet(payslipData);
  if (!data) return null;
  const recup = objet(objet(objet(data.pied_de_page)?.solde_conges)?.recuperation);
  const mod = objet(data.modulation_account) ?? {};
  const regle =
    mod.regle === 'account_all' ? 'compteur' : mod.regle === 'pay_all' ? 'payees' : 'autre';
  const heuresDuMois = nombre(mod.hs_realisees);
  if (!recup && !(regle === 'payees' && heuresDuMois > 0)) return null;
  return {
    heuresSupDuMois: heuresDuMois,
    heuresSupAuCompteur: nombre(mod.hs_credited),
    reposCredite: nombre(mod.repos_credite),
    payeesCeMois: mod.paye_ce_mois === true,
    auCompteurCeMois: mod.au_compteur_ce_mois === true,
    solde: nombre(recup?.solde),
    soldePaye: nombre(recup?.paye),
    soldePayable: nombre(recup?.payable),
    regle,
  };
}

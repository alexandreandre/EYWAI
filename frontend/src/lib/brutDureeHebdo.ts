/** Brut mensuel pour la durée du contrat.

Deux lectures du salaire saisi, comme le moteur
(`specificites_paie.salaire_hors_hs_structurelles`) :
- base à 35 h : on ajoute les heures au-delà de 35 h majorées au taux du barème, même
  arrondi que `salaire_contractuel_total_hors_hs_mode` ;
- sinon le montant saisi est déjà le brut pour la durée du contrat.
39 h donnent 169 h dans le mois. */

import type { RatesResponse } from '@/api/rates';

const DUREE_LEGALE = 35;
/** Repli tant que le barème n'est pas lu ; le moteur, lui, lit toujours le barème. */
const MAJORATION_PAR_DEFAUT = 0.25;

/**
 * Taux de la première tranche du barème des heures supplémentaires, celui que
 * le moteur applique aux heures structurelles (`calcul_brut._taux_majoration_hs`).
 * L'écran figeait 25 % ([B15], 12/10/2026).
 */
export function majorationHsDuBareme(rates: Partial<RatesResponse> | null | undefined): number | null {
  const config = rates?.heures_supp?.config_data as
    | { regles_calcul_communes?: { taux_majoration_par_defaut?: { heures_supplementaires?: { taux?: unknown }[] } } }
    | undefined;
  const taux = config?.regles_calcul_communes?.taux_majoration_par_defaut?.heures_supplementaires?.[0]?.taux;
  const valeur = typeof taux === 'string' ? Number(taux) : taux;
  return typeof valeur === 'number' && Number.isFinite(valeur) ? valeur : null;
}

/** « majorées de 25 % », ou le renvoi au barème tant qu'on ne l'a pas lu. */
export function texteMajoration(majoration: number | null | undefined): string {
  if (majoration == null) return 'majorées au taux du barème des heures supplémentaires';
  const pourcent = Math.round(majoration * 10000) / 100;
  return `majorées de ${pourcent.toLocaleString('fr-FR')}\u00a0%`;
}

function round2(valeur: number): number {
  return Math.round(valeur * 100) / 100;
}

export function brutMensuelPourDuree(
  salaireBase: number,
  dureeHebdo: number,
  baseA35h: boolean,
  majoration: number | null = MAJORATION_PAR_DEFAUT,
): { heures: number; brut: number; baseA35h: boolean } | null {
  if (!Number.isFinite(salaireBase) || salaireBase <= 0) return null;
  if (!Number.isFinite(dureeHebdo) || dureeHebdo <= DUREE_LEGALE) return null;
  const heures = round2((dureeHebdo * 52) / 12);
  if (!baseA35h) return { heures, brut: round2(salaireBase), baseA35h };
  const heuresLegales = round2((DUREE_LEGALE * 52) / 12);
  const heuresSup = round2(((dureeHebdo - DUREE_LEGALE) * 52) / 12);
  const taux = salaireBase / heuresLegales;
  const partHs = round2(heuresSup * taux * (1 + (majoration ?? MAJORATION_PAR_DEFAUT)));
  return { heures, brut: round2(salaireBase + partHs), baseA35h };
}

export function formaterEuros(montant: number): string {
  return montant.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

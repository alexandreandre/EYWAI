/** Brut mensuel pour la durée du contrat, à partir du salaire de base à 35 h.

Même arrondi que `salaire_contractuel_total_hors_hs_mode` : les heures
au-delà de 35 h sont majorées de 25 %. 39 h donnent 169 h dans le mois. */

const DUREE_LEGALE = 35;
const MAJORATION = 0.25;

function round2(valeur: number): number {
  return Math.round(valeur * 100) / 100;
}

export function brutMensuelPourDuree(
  salaireBase: number,
  dureeHebdo: number,
): { heures: number; brut: number } | null {
  if (!Number.isFinite(salaireBase) || salaireBase <= 0) return null;
  if (!Number.isFinite(dureeHebdo) || dureeHebdo <= DUREE_LEGALE) return null;
  const heures = round2((dureeHebdo * 52) / 12);
  const heuresLegales = round2((DUREE_LEGALE * 52) / 12);
  const heuresSup = round2(((dureeHebdo - DUREE_LEGALE) * 52) / 12);
  const taux = salaireBase / heuresLegales;
  const partHs = round2(heuresSup * taux * (1 + MAJORATION));
  return { heures, brut: round2(salaireBase + partHs) };
}

export function formaterEuros(montant: number): string {
  return montant.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

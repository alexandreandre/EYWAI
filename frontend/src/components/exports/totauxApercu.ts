/**
 * Les montants de l'aperçu d'un export.
 *
 * « Montant total » affichait le net à payer pour tous les exports, alors que
 * le serveur calcule le montant propre à chacun (total des écritures d'une OD
 * ou du FEC, montant à virer…), et « Totaux de contrôle » restait un cadre vide
 * avec une coche verte pour le virement (relevé I.1 et I.2 du 12/10/2026).
 */

import type { ExportTotals, ExportType } from '@/api/exports';

export type MontantAffiche = { libelle: string; texte: string };

const ECRITURES: ReadonlySet<ExportType> = new Set<ExportType>([
  'od_salaires',
  'od_charges_sociales',
  'od_pas',
  'od_globale',
  'fec',
  'export_cabinet_generique',
  'export_cabinet_quadra',
  'export_cabinet_sage',
]);

const LIBELLES: Partial<Record<ExportType, string>> = {
  journal_paie: 'Total net à payer',
  recapitulatif_montants: 'Total net à payer',
  virement_salaires: 'Montant à virer',
  virement_acomptes: 'Montant à virer',
  paiement_organismes: 'Montant à payer',
  charges_sociales: 'Total des cotisations',
  dsn_mensuelle: 'Masse salariale brute',
};

function euros(montant: number): string {
  return montant.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
}

function nombre(valeur: number): string {
  return valeur.toLocaleString('fr-FR', { maximumFractionDigits: 2 });
}

/** Le montant de l'export et son nom ; null quand le serveur n'en donne pas. */
export function montantDeLApercu(type: ExportType, totals: ExportTotals): MontantAffiche | null {
  if (type === 'conges_absences') {
    // Le serveur y met des jours, pas des euros.
    const jours = totals.total_amount;
    if (jours == null) return null;
    return { libelle: 'Jours d’absence', texte: `${nombre(jours)} ${jours >= 2 ? 'jours' : 'jour'}` };
  }
  if (ECRITURES.has(type)) {
    if (totals.total_amount == null) return null;
    return { libelle: 'Total des écritures (débit)', texte: euros(totals.total_amount) };
  }
  const montant =
    type === 'journal_paie'
      ? (totals.total_net_a_payer ?? totals.total_amount)
      : (totals.total_amount ?? totals.total_net_a_payer);
  if (montant == null) return null;
  return { libelle: LIBELLES[type] ?? 'Montant total', texte: euros(montant) };
}

export type LigneDeControle = { libelle: string; texte: string };

/** Les totaux de contrôle de l'export ; vide quand il n'en a pas (le cadre se cache). */
export function lignesTotauxDeControle(type: ExportType, totals: ExportTotals): LigneDeControle[] {
  const lignes: LigneDeControle[] = [];
  if (type === 'acomptes' || type === 'saisies') {
    if (type === 'acomptes' && totals.total_versements != null) {
      lignes.push({ libelle: 'Total versements', texte: euros(totals.total_versements) });
    }
    if (type === 'acomptes' && totals.total_remboursements != null) {
      lignes.push({ libelle: 'Total remboursements', texte: euros(totals.total_remboursements) });
    }
    if (type === 'saisies' && totals.total_prelevements != null) {
      lignes.push({ libelle: 'Total prélèvements', texte: euros(totals.total_prelevements) });
    }
    if (totals.operations_count != null) {
      lignes.push({ libelle: 'Opérations', texte: nombre(totals.operations_count) });
    }
    return lignes;
  }
  if (totals.total_brut != null) {
    lignes.push({ libelle: 'Total brut', texte: euros(totals.total_brut) });
  }
  if (totals.total_cotisations_salariales != null || totals.total_cotisations_patronales != null) {
    lignes.push({
      libelle: 'Total cotisations',
      texte: euros(
        (totals.total_cotisations_salariales ?? 0) + (totals.total_cotisations_patronales ?? 0)
      ),
    });
  }
  if (totals.total_net_a_payer != null) {
    lignes.push({ libelle: 'Total net', texte: euros(totals.total_net_a_payer) });
  }
  return lignes;
}

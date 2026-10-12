// La bascule de reprise d'une société, dite en clair ([B13], 12/10/2026).
// « Source de paie » est un réglage des alertes DSN, pas l'état de la reprise.

export interface ReprisePaie {
  dernier_mois_repris: string;
  premier_mois_calcule: string;
  logiciel_precedent?: string | null;
  source?: string | null;
}

const MOIS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

function dernierJour(periode: string): string {
  const [annee, mois] = periode.split('-').map(Number);
  const jour = new Date(Date.UTC(annee, mois, 0)).getUTCDate();
  return `${String(jour).padStart(2, '0')}/${String(mois).padStart(2, '0')}/${annee}`;
}

function moisEnLettres(periode: string): string {
  const [annee, mois] = periode.split('-');
  return `${MOIS[Number(mois) - 1] ?? mois} ${annee}`;
}

export function libelleBascule(reprise: ReprisePaie | null | undefined): string {
  if (!reprise) {
    return 'Aucune reprise posée : ni date de bascule, ni solde d’ouverture repris d’un ancien logiciel.';
  }
  const logiciel = reprise.logiciel_precedent?.trim() || 'l’ancien logiciel';
  return `Paie reprise de ${logiciel} au ${dernierJour(reprise.dernier_mois_repris)} : Martine calcule la paie depuis ${moisEnLettres(reprise.premier_mois_calcule)}.`;
}

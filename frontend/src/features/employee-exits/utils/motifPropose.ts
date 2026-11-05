/**
 * Motif de départ proposé d'office : un CDD qui porte sa date de fin finit à
 * son terme, c'est une fin de CDD. Martine pré-remplit, la RH peut changer ;
 * rien ne bloque. Même lecture que le bandeau de la Paie (sortieGuidee).
 */

export type SalariePourMotifPropose = {
  contract_type?: string | null;
  contract_end_date?: string | null;
};

export type MotifPropose = {
  motif: 'fin_cdd';
  dernierJour: string;
  phrase: string;
};

function jourIso(valeur?: string | null): string | null {
  const iso = (valeur || '').slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(iso) ? iso : null;
}

export function motifProposeAuDepart(salarie?: SalariePourMotifPropose | null): MotifPropose | null {
  if (!salarie) return null;
  const type = (salarie.contract_type || '').trim().toUpperCase();
  const fin = jourIso(salarie.contract_end_date);
  if (type !== 'CDD' || !fin) return null;
  const [annee, mois, jour] = fin.split('-');
  return {
    motif: 'fin_cdd',
    dernierJour: fin,
    phrase: `Proposé par Martine : CDD qui finit le ${jour}/${mois}/${annee}.`,
  };
}

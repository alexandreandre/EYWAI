/**
 * Motif de départ proposé d'office : un contrat à terme qui porte sa date de
 * fin (CDD, apprentissage…) finit à son terme, c'est une fin de CDD. Martine
 * pré-remplit, la RH peut changer ; rien ne bloque. Même lecture de la date que
 * le bandeau de la Paie (sortieGuidee), un CDI mis à part.
 */

import { dateDeFinDuContrat } from '@/features/payroll/utils/sortieGuidee';

export type SalariePourMotifPropose = {
  contract_type?: string | null;
  contract_end_date?: string | null;
};

export type MotifPropose = {
  motif: 'fin_cdd';
  dernierJour: string;
  phrase: string;
};

export function motifProposeAuDepart(salarie?: SalariePourMotifPropose | null): MotifPropose | null {
  if (!salarie) return null;
  const type = (salarie.contract_type || '').trim().toUpperCase();
  const fin = dateDeFinDuContrat({ contract_end_date: salarie.contract_end_date });
  if (type === 'CDI' || !fin) return null;
  const [annee, mois, jour] = fin.split('-');
  const contrat = type === 'CDD' ? 'CDD' : 'contrat';
  return {
    motif: 'fin_cdd',
    dernierJour: fin,
    phrase: `Proposé par Martine : ${contrat} qui finit le ${jour}/${mois}/${annee}.`,
  };
}

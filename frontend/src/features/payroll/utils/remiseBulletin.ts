/**
 * Remise du bulletin au salarié (D4, D5) : la société règle le jour où il voit
 * son bulletin validé ; dès ce jour, le bulletin ne se modifie plus. Une fois
 * remis, le verrou de correction le dit (`manual_edit_lock_reason`).
 */

import { dateEnClair } from '@/components/payslip/comparaisonAffichage';

interface RemiseDuBulletin {
  status?: 'brouillon' | 'valide';
  remis_le?: string | null;
  bulletin_remis?: boolean;
}

/** La phrase d'un bulletin validé que le salarié ne voit pas encore ; null sinon. */
export function phraseRemise(bulletin: RemiseDuBulletin): string | null {
  if (bulletin.status !== 'valide' || !bulletin.remis_le || bulletin.bulletin_remis) return null;
  return (
    `Visible par le salarié le ${dateEnClair(bulletin.remis_le)}. Jusque-là, il se corrige ` +
    'encore ; ensuite, une erreur se corrige sur le bulletin du mois suivant.'
  );
}

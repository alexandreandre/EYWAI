import { describe, expect, it } from 'vitest';

import { aujourdhuiLocal, dateDeDemandeProposee } from './dateDeDemande';

/**
 * La base impose, pour tout départ, une date de demande au plus tard le dernier
 * jour travaillé (contrainte employee_exits_check). Proposer la date du jour à
 * une fin de CDD déjà passée (tournage H.1, 20/10/2026) faisait échouer
 * l'enregistrement en 502 « Erreur base de données » : la date reste plafonnée
 * au dernier jour, quel que soit le type de départ.
 */
describe('date de demande/notification proposée', () => {
  it('dernier jour déjà passé (une fin de CDD au 15/10 créée le 20/10) : plafonnée au dernier jour', () => {
    expect(dateDeDemandeProposee({ aujourdHui: '2026-10-20', dernierJour: '2026-10-15' })).toBe('2026-10-15');
  });

  it('dernier jour à venir ou inconnu : la date du jour', () => {
    expect(dateDeDemandeProposee({ aujourdHui: '2026-10-20', dernierJour: '2026-10-31' })).toBe('2026-10-20');
    expect(dateDeDemandeProposee({ aujourdHui: '2026-10-20', dernierJour: undefined })).toBe('2026-10-20');
  });

  it('la date du jour est celle du fuseau de l’écran, pas celle de UTC', () => {
    expect(aujourdhuiLocal(new Date(2026, 9, 21, 0, 30))).toBe('2026-10-21');
  });
});

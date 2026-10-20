import { describe, expect, it } from 'vitest';

import { aujourdhuiLocal, dateDeDemandeProposee, notificationAvantLaFin } from './dateDeDemande';

/**
 * Tournage H.1, scène 4 (20/10/2026) : fin de CDD au 15/10 créée le 20/10, la
 * « Date de demande/notification » reprenait le dernier jour travaillé au lieu
 * de la date du jour. La date du jour est proposée ; elle ne dépasse le dernier
 * jour que pour une fin de CDD, qui n'a ni notification (DSN : pas de date de
 * notification pour les motifs 031 et 081), ni préavis, ni indemnité qui en
 * dépende. Une démission, un licenciement, une rupture, une retraite ou une fin
 * de période d'essai se notifient avant la fin : la date reste plafonnée au
 * dernier jour.
 */
describe('date de demande/notification proposée', () => {
  it('fin de CDD déjà passée : la date du jour', () => {
    expect(dateDeDemandeProposee({ aujourdHui: '2026-10-20', dernierJour: '2026-10-15', exitType: 'fin_cdd' })).toBe(
      '2026-10-20'
    );
  });

  it.each(['demission', 'licenciement', 'rupture_conventionnelle', 'depart_retraite', 'fin_periode_essai', 'transfert'])(
    '%s au dernier jour passé : plafonnée au dernier jour',
    (exitType) => {
      expect(dateDeDemandeProposee({ aujourdHui: '2026-10-20', dernierJour: '2026-10-15', exitType })).toBe('2026-10-15');
    }
  );

  it('dernier jour à venir ou inconnu : la date du jour', () => {
    expect(dateDeDemandeProposee({ aujourdHui: '2026-10-20', dernierJour: '2026-10-31', exitType: 'demission' })).toBe(
      '2026-10-20'
    );
    expect(dateDeDemandeProposee({ aujourdHui: '2026-10-20', dernierJour: undefined, exitType: 'fin_cdd' })).toBe(
      '2026-10-20'
    );
  });

  it('seule une fin de CDD peut être enregistrée après son dernier jour', () => {
    expect(notificationAvantLaFin('fin_cdd')).toBe(false);
    expect(notificationAvantLaFin('demission')).toBe(true);
  });

  it('la date du jour est celle du fuseau de l’écran, pas celle de UTC', () => {
    expect(aujourdhuiLocal(new Date(2026, 9, 21, 0, 30))).toBe('2026-10-21');
  });
});

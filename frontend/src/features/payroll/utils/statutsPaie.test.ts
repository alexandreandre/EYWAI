import { describe, expect, it } from 'vitest';

import { MESSAGE_STATUTS_PRIS_EN_COMPTE, libelleStatutSalarie, statutPermetLaPaie } from './statutsPaie';

describe('statuts de salarié et paie', () => {
  it('seul un salarié actif peut être payé, comme le refuse le serveur', () => {
    expect(statutPermetLaPaie('actif')).toBe(true);
    expect(statutPermetLaPaie('active')).toBe(true);
    expect(statutPermetLaPaie(undefined)).toBe(true);
    expect(statutPermetLaPaie('en_onboarding')).toBe(false);
    expect(statutPermetLaPaie('suspendu')).toBe(false);
  });

  it('le texte de l’écran ne promet pas l’onboarding', () => {
    expect(MESSAGE_STATUTS_PRIS_EN_COMPTE).toContain('Actif');
    expect(MESSAGE_STATUTS_PRIS_EN_COMPTE).toContain('onboarding');
    expect(MESSAGE_STATUTS_PRIS_EN_COMPTE).not.toMatch(/Actif et .*onboarding.* sont pris/);
  });

  it('les statuts sont dits en français, jamais en code', () => {
    expect(libelleStatutSalarie('en_sortie')).toBe('En départ');
    expect(libelleStatutSalarie('suspendu')).toBe('Suspendu');
    expect(libelleStatutSalarie('autre_chose')).toBe('Statut inconnu');
  });
});

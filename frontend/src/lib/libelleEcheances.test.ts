import { describe, expect, it } from 'vitest';

import { TITRE_ECHEANCES, messageEcheances } from './libelleEcheances';

describe('décompte des échéances', () => {
  it('dit tout ce qu’il compte, titres de séjour compris, avec leur fenêtre', () => {
    expect(TITRE_ECHEANCES).toContain('CDD');
    expect(TITRE_ECHEANCES).toContain('stage');
    expect(TITRE_ECHEANCES).toContain('périodes d’essai');
    expect(TITRE_ECHEANCES).toContain('titres de séjour');
    expect(TITRE_ECHEANCES).toContain('30 jours');
  });

  it('accorde le message au nombre', () => {
    expect(messageEcheances(0)).toBe('Aucune échéance à venir.');
    expect(messageEcheances(1)).toBe('1 salarié à traiter.');
    expect(messageEcheances(3)).toBe('3 salariés à traiter.');
  });
});

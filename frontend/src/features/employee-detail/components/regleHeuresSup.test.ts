import { describe, expect, it } from 'vitest';

import {
  choixDeLaRegle,
  phraseDuChoix,
  phraseSalariesReglePropre,
  regleDuChoix,
} from './regleHeuresSup';

describe('règle des heures sup du salarié', () => {
  it('null en base = règle de la société, et retour', () => {
    expect(choixDeLaRegle(null)).toBe('societe');
    expect(regleDuChoix('societe')).toBeNull();
    expect(regleDuChoix(choixDeLaRegle('pay_all'))).toBe('pay_all');
    expect(regleDuChoix(choixDeLaRegle('account_all'))).toBe('account_all');
  });

  it('la phrase dit la règle de la société quand le salarié la suit', () => {
    expect(phraseDuChoix('societe', 'franchise')).toBe(
      'Comme les autres salariés : les premières heures sup du mois au compteur, le reste payé.',
    );
    expect(phraseDuChoix('pay_all', 'account_all')).toMatch(/payées sur son bulletin chaque mois/);
    expect(phraseDuChoix('account_all', 'pay_all')).toMatch(/toujours à son compteur/);
  });

  it('la ligne de la société ne parle que s’il y a quelqu’un', () => {
    expect(phraseSalariesReglePropre(0)).toBeNull();
    expect(phraseSalariesReglePropre(undefined)).toBeNull();
    expect(phraseSalariesReglePropre(1)).toMatch(/^1 salarié suit une autre règle/);
    expect(phraseSalariesReglePropre(3)).toMatch(/^3 salariés suivent une autre règle/);
  });
});

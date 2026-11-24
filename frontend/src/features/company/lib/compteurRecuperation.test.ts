import { describe, expect, it } from 'vitest';
import {
  etatInterrupteurCompteur,
  phraseCompteurCoupe,
  reglageCompteur,
} from './compteurRecuperation';

describe('etatInterrupteurCompteur', () => {
  it('heures sup payées, compteur coupé : allumable', () => {
    const e = etatInterrupteurCompteur({
      hour_account_enabled: false,
      recovery_absence_enabled: true,
      hs_routing_policy: 'pay_all',
    });
    expect(e).toMatchObject({ allume: false, modifiable: true });
    expect(e.explication).toContain('restent payées');
  });

  it('heures sup payées, compteur tenu : coupable, et dit ce que la coupure masque', () => {
    const e = etatInterrupteurCompteur({
      hour_account_enabled: true,
      recovery_absence_enabled: true,
      hs_routing_policy: 'pay_all',
    });
    expect(e).toMatchObject({ allume: true, modifiable: true });
    expect(e.explication).toContain('soldes saisis restent enregistrés');
  });

  it('heures sup payées, un salarié toujours au compteur : le compteur ne se coupe pas', () => {
    const e = etatInterrupteurCompteur({
      hour_account_enabled: true,
      recovery_absence_enabled: true,
      hs_routing_policy: 'pay_all',
      salaries_toujours_au_compteur: 1,
    });
    expect(e).toMatchObject({ allume: true, modifiable: false });
    expect(e.explication).toContain('1 salarié a ses heures sup « toujours au compteur »');
  });

  it('compteur ouvert sans les repos pris : compté comme éteint, pour tout rallumer', () => {
    const e = etatInterrupteurCompteur({
      hour_account_enabled: true,
      recovery_absence_enabled: false,
      hs_routing_policy: 'pay_all',
    });
    expect(e.allume).toBe(false);
  });

  it('heures sup au compteur : toujours tenu, non modifiable', () => {
    for (const policy of ['account_all', 'franchise', 'manual'] as const) {
      const e = etatInterrupteurCompteur({
        hour_account_enabled: true,
        recovery_absence_enabled: true,
        hs_routing_policy: policy,
      });
      expect(e).toMatchObject({ allume: true, modifiable: false });
      expect(e.explication).toContain('Payées au bulletin');
    }
  });
});

describe('reglageCompteur', () => {
  it('allumé depuis « Payées », pose la règle « payées » (le défaut en base est la franchise)', () => {
    expect(reglageCompteur(true, { hour_account_enabled: false, hs_routing_policy: 'franchise' })).toEqual({
      hour_account_enabled: true,
      recovery_absence_enabled: true,
      hs_routing_policy: 'pay_all',
    });
    expect(reglageCompteur(true, { hour_account_enabled: true, hs_routing_policy: 'pay_all' })).toEqual({
      hour_account_enabled: true,
      recovery_absence_enabled: true,
      hs_routing_policy: 'pay_all',
    });
  });
  it('ne touche jamais une règle « au compteur » déjà choisie, ni à l’extinction', () => {
    expect(reglageCompteur(true, { hour_account_enabled: true, hs_routing_policy: 'franchise' })).not.toHaveProperty(
      'hs_routing_policy',
    );
    expect(reglageCompteur(false, { hour_account_enabled: true, hs_routing_policy: 'pay_all' })).not.toHaveProperty(
      'hs_routing_policy',
    );
  });
});

describe('phraseCompteurCoupe', () => {
  it('dit où allumer le compteur quand il est coupé', () => {
    const p = phraseCompteurCoupe({
      hour_account_enabled: false,
      recovery_absence_enabled: true,
      hs_routing_policy: 'pay_all',
    });
    expect(p).toContain('Tenir un compteur de récupération');
    expect(p).toContain('Heures supplémentaires');
  });

  it('rien quand le compteur est tenu, ni avant la lecture du réglage', () => {
    expect(
      phraseCompteurCoupe({
        hour_account_enabled: true,
        recovery_absence_enabled: true,
        hs_routing_policy: 'pay_all',
      }),
    ).toBeNull();
    expect(phraseCompteurCoupe(undefined)).toBeNull();
  });
});

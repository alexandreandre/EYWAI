import { describe, expect, it } from 'vitest';
import {
  appliquerRegleALaRevue,
  deductedBreakMinutes,
  netHoursFromRange,
  reapplyPauseOnHours,
  type PunchBreakRule,
} from './punchBreakHours';

const pause30: PunchBreakRule = {
  enabled: true,
  breakMinutes: 30,
  thresholdMinutes: 360,
};

const none: PunchBreakRule = {
  enabled: false,
  breakMinutes: 30,
  thresholdMinutes: 360,
};

describe('deductedBreakMinutes', () => {
  it('déduit 30 min au-delà du seuil de présence', () => {
    expect(deductedBreakMinutes(9 * 60, pause30)).toBe(30);
  });

  it('n’ôte rien sur une demi-journée sous le seuil', () => {
    expect(deductedBreakMinutes(5 * 60, pause30)).toBe(0);
  });

  it('n’ôte rien si le moteur est inactif', () => {
    expect(deductedBreakMinutes(9 * 60, none)).toBe(0);
  });
});

describe('netHoursFromRange', () => {
  it('recalcule 07:00–16:00 avec pause 30 min', () => {
    expect(netHoursFromRange('07:00', '16:00', pause30)).toBe(8.5);
  });

  it('garde le brut si le moteur est inactif', () => {
    expect(netHoursFromRange('07:00', '16:00', none)).toBe(9);
  });
});

describe('reapplyPauseOnHours', () => {
  it('ajoute 0,5 h quand on retire la pause de 30 min sur une journée nette', () => {
    expect(reapplyPauseOnHours(8.5, pause30, none)).toBe(9);
  });

  it('ne touche pas une journée trop courte pour la pause', () => {
    expect(reapplyPauseOnHours(5, pause30, none)).toBe(5);
  });
});

describe('appliquerRegleALaRevue : la règle de pause changée pendant la revue', () => {
  const avant = { enabled: true, breakMinutes: 45, thresholdMinutes: 0 };
  const apres = { enabled: true, breakMinutes: 30, thresholdMinutes: 0 };
  const jour = { heures: 7, type: 'travail', punch_entry_raw: '728', punch_exit_raw: '1555' };

  it("avec des horaires (créneaux), les heures ne sont pas recalculées à l'écran, et un avis le dit", () => {
    const r = appliquerRegleALaRevue([jour], avant, apres, true);
    expect(r.days).toEqual([jour]);
    expect(r.avis).toMatch(/pas recalculées ici/);
    expect(r.avis).toMatch(/Refaites l.import/);
  });

  it('sans horaires, les heures suivent les badges moins la nouvelle pause, sans avis', () => {
    const r = appliquerRegleALaRevue([jour], avant, apres, false);
    expect(r.days[0].heures).toBe(7.95);
    expect(r.avis).toBeNull();
  });
});

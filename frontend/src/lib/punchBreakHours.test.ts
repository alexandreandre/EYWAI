import { describe, expect, it } from 'vitest';
import {
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

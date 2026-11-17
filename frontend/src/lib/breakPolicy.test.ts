import { describe, expect, it } from 'vitest';

import {
  aUnDetailDePauses,
  breaksFromLegacy,
  INDUSTRIAL_2X10_MEAL_30,
  libellePausesPayees,
} from './breakPolicy';


describe('plusieurs pauses dans le modèle de semaine (Lyon, 17/11)', () => {
  it('le détail de plusieurs pauses ne se remplace pas par la colonne', () => {
    expect(aUnDetailDePauses(INDUSTRIAL_2X10_MEAL_30)).toBe(true);
    expect(aUnDetailDePauses(breaksFromLegacy(30, false))).toBe(false);
    expect(libellePausesPayees(INDUSTRIAL_2X10_MEAL_30)).toBe('En partie');
  });
});

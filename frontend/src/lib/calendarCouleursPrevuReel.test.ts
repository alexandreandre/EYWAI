import { describe, expect, it } from 'vitest';

import { CALENDAR_TYPE_BAR_COLORS, COULEUR_PREVU, COULEUR_REEL } from '@/lib/calendarTypes';

// Retour d'Elsa (28/10, vidéo C1 à 4:56) : « Travail » et « Prévu » avaient le
// même bleu ; elle demande un orange et un bleu.
describe('couleurs du prévu et du réel', () => {
  const teinte = (classe: string) => classe.split('-')[1];

  it('le prévu est orange, distinct du bleu du travail', () => {
    expect(teinte(COULEUR_PREVU.texte)).toBe('orange');
    expect(teinte(COULEUR_PREVU.texte)).not.toBe(teinte(CALENDAR_TYPE_BAR_COLORS.travail));
  });

  it('le réel ne prend ni la teinte du prévu ni celle du travail', () => {
    expect(teinte(COULEUR_REEL.texte)).not.toBe(teinte(COULEUR_PREVU.texte));
    expect(teinte(COULEUR_REEL.texte)).not.toBe(teinte(CALENDAR_TYPE_BAR_COLORS.travail));
  });
});

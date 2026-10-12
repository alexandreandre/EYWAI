import { describe, expect, it } from 'vitest';

import { AIDE_STATUT_PAS, periodeDuTaux, resumeCompteursPas } from '@/features/pas-rates/lib/statutsPas';

describe('statut et compteurs des taux sur la page ([B3], 12/10/2026)', () => {
  it('résume les compteurs du plus alarmant au plus rassurant, sans les zéros', () => {
    expect(
      resumeCompteursPas({ total: 6, a_jour: 3, bareme: 1, a_rafraichir: 0, manquant: 2 }),
    ).toBe('2 manquants · 1 au barème par défaut · 3 à jour');
  });

  it('un seul compteur au singulier', () => {
    expect(resumeCompteursPas({ total: 1, manquant: 1 })).toBe('1 manquant');
    expect(resumeCompteursPas({ total: 1, a_rafraichir: 1 })).toBe('1 à rafraîchir');
  });

  it('« Manquant » dit que la grille s’applique, pas 0 %', () => {
    expect(AIDE_STATUT_PAS.manquant).toContain('grille par défaut');
    expect(AIDE_STATUT_PAS.manquant).not.toContain('0 %');
  });
});

describe('période du taux sur la fiche ([B3])', () => {
  it('lit l’historique daté quand la date du bloc a été effacée', () => {
    expect(
      periodeDuTaux({ taux: 4.3, type_taux: '01' }, [
        { periode: '2026-05' },
        { periode: '2026-06' },
      ]),
    ).toBe('2026-06');
  });

  it('l’historique passe avant le bloc, comme sur la page des taux', () => {
    expect(periodeDuTaux({ taux: 4.3, periode: '2026-03' }, [{ periode: '2026-06' }])).toBe('2026-06');
  });

  it('sans historique, la date du bloc ; sans rien, aucune', () => {
    expect(periodeDuTaux({ taux: 4.3, periode: '2026-03' }, [])).toBe('2026-03');
    expect(periodeDuTaux({ taux: 4.3 }, undefined)).toBeNull();
  });
});

import { describe, expect, it } from 'vitest';

import { prevoyanceFicheSchema } from '@/features/employees/utils/prevoyanceSchema';

// Défaut trouvé le 02/11/2026 : le schéma des lignes retirait `base`. Une ligne
// sur la tranche B (15 fiches dans les 7 sociétés) repassait en tranche A au
// premier enregistrement de la fiche, sans un mot.
describe('prévoyance de la fiche', () => {
  const ligneTB = {
    id: 'prevoyance_2',
    libelle: 'Prévoyance cadre TB',
    salarial: 0.01,
    patronal: 0.012,
    forfait_social: 0.08,
    base: 'tranche_2',
  };

  it('garde la base d’une ligne et ses autres clés', () => {
    const lue = prevoyanceFicheSchema.parse({ adhesion: true, lignes_specifiques: [{ ...ligneTB, organisme: 'X' }] });
    expect(lue.lignes_specifiques[0]).toMatchObject({ base: 'tranche_2', organisme: 'X' });
  });

  it('garde la formule d’où viennent les lignes', () => {
    expect(prevoyanceFicheSchema.parse({ adhesion: true, formule_id: 'f1' }).formule_id).toBe('f1');
    expect(prevoyanceFicheSchema.parse({ adhesion: true, formule_id: null }).formule_id).toBeNull();
  });

  it('accepte une ligne sans forfait social (il suit la loi, pas la ligne)', () => {
    const { forfait_social: _fs, ...sansForfait } = ligneTB;
    expect(prevoyanceFicheSchema.safeParse({ adhesion: true, lignes_specifiques: [sansForfait] }).success).toBe(true);
  });

  it('refuse toujours une ligne sans libellé', () => {
    expect(prevoyanceFicheSchema.safeParse({ adhesion: true, lignes_specifiques: [{ ...ligneTB, libelle: '' }] }).success).toBe(false);
  });
});

import { describe, expect, it } from 'vitest';
import { MOTIF_PROPOSE, phraseMotifDsn, valeurMotifDsn } from './motifDsn';
import type { MotifDsnDossier } from '@/api/employeeExits';

const options = [{ code: '037', libelle: 'Rupture anticipée du CDD à l’initiative du salarié' }];
const base: MotifDsnDossier = { choisi: null, propose: null, retenu: null, alerte: null, options };

describe('motif DSN du dossier de sortie', () => {
  it('dit ce qu’il reste à faire quand rien ne peut être proposé', () => {
    expect(phraseMotifDsn({ ...base, alerte: 'Choisissez le motif.' })).toBe('Choisissez le motif.');
    expect(valeurMotifDsn(base)).toBe(MOTIF_PROPOSE);
  });
  it('dit le motif retenu', () => {
    expect(phraseMotifDsn({ ...base, choisi: '037', retenu: '037' })).toContain('037');
    expect(phraseMotifDsn({ ...base, propose: '037', retenu: '037' })).toContain('Proposé par Martine');
    expect(valeurMotifDsn({ ...base, choisi: '037' })).toBe('037');
  });
});

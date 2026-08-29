import { describe, expect, it } from 'vitest';
import {
  assistedFillDialogHeightClass,
  removeReviewRow,
  showReviewSummaryBanner,
} from './assistedFillReviewLayout';

describe('assistedFillDialogHeightClass', () => {
  it('fixe une hauteur définie en revue pour que la liste des jours défile', () => {
    expect(assistedFillDialogHeightClass(true)).toContain('h-[90dvh]');
  });

  it('laisse le formulaire consigne s’ajuster au contenu', () => {
    const classes = assistedFillDialogHeightClass(false);
    expect(classes).toContain('max-h-[90dvh]');
    expect(classes.split(/\s+/)).not.toContain('h-[90dvh]');
  });
});

describe('showReviewSummaryBanner', () => {
  it('masque Consigne texte, le badge N prêts et la phrase de vérification', () => {
    expect(showReviewSummaryBanner({ source: 'texte' })).toBe(false);
  });

  it('conserve le bandeau pour un import fichier ou PDF', () => {
    expect(showReviewSummaryBanner({ source: 'pdf' })).toBe(true);
    expect(showReviewSummaryBanner({ source: 'excel' })).toBe(true);
  });
});

describe('removeReviewRow', () => {
  it('retire uniquement la ligne lue ciblée', () => {
    const rows = [{ key: '0-AURELIEN' }, { key: '1-Hugo' }, { key: '2-Michel' }];
    expect(removeReviewRow(rows, '0-AURELIEN').map((r) => r.key)).toEqual([
      '1-Hugo',
      '2-Michel',
    ]);
  });

  it('ne change rien si la clé est inconnue', () => {
    const rows = [{ key: '1-Hugo' }];
    expect(removeReviewRow(rows, 'missing')).toEqual(rows);
  });
});

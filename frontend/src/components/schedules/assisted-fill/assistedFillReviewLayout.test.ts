import { describe, expect, it } from 'vitest';
import {
  assistedFillDialogHeightClass,
  mentionSourceRevue,
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
  it('garde le bandeau (mention de source, pastille « N prêts ») pour toute consigne texte, avant comme après une correction', () => {
    // La première analyse peut dire « texte (analyse rapide) », la correction « texte » :
    // le bandeau ne doit pas disparaître au changement de chemin.
    for (const source of ['texte', 'texte (analyse rapide)', 'texte (saisie collective)', 'texte (reprise planning)']) {
      expect(showReviewSummaryBanner({ source })).toBe(true);
    }
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

describe('mentionSourceRevue', () => {
  it('consigne écrite (même collective) : proposition à relire, pas de PDF', () => {
    for (const source of ['texte', 'texte (saisie collective)']) {
      const m = mentionSourceRevue({ source, detected_format: null });
      expect(m?.texte).toBe('Proposition établie d’après votre consigne : relisez-la avant d’enregistrer.');
      expect(m?.texte).not.toContain('PDF');
    }
  });

  it('PDF ou photo : les noms lus peuvent être erronés', () => {
    expect(mentionSourceRevue({ source: 'pdf', detected_format: null })?.texte).toBe(
      'Import IA — les noms lus sur le PDF peuvent être erronés.',
    );
  });

  it('fichier tableur : associer à la main les salariés non reconnus', () => {
    expect(mentionSourceRevue({ source: 'csv', detected_format: 'tabular_csv' })?.texte).toBe(
      'Import fichier — associez manuellement les salariés non reconnus si besoin.',
    );
  });
});

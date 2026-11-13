import { describe, expect, it } from 'vitest';
import { calendarSaveFailureMessage } from './calendarSaveFeedback';

describe('refus d’enregistrement du calendrier', () => {
  it('affiche le conflit métier sans effacer ni remplacer les saisies', () => {
    expect(calendarSaveFailureMessage({ response: { data: { detail: {
      code: 'calendar_conflict', message: 'Ce calendrier a changé. Vos saisies restent affichées.',
    } } } })).toContain('Vos saisies restent affichées');
  });
  it('distingue le réel non confirmé après un prévu confirmé', () => {
    const message = calendarSaveFailureMessage({ response: { data: { detail: {
      code: 'calendar_save_failed', stage: 'actual', confirmed: ['planned'],
    } } } });
    expect(message).toContain('Le prévu a été enregistré');
    expect(message).toContain('le réel n’a pas pu être confirmé');
  });
  it('ne promet pas une absence d’écriture lors d’une réponse réseau perdue', () => {
    const message = calendarSaveFailureMessage(new Error('timeout'));
    expect(message).toContain('n’a pas pu être confirmé');
    expect(message).toContain('conservez-les');
  });
});

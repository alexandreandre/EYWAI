import { describe, expect, it } from 'vitest';
import { descriptionAffichable } from './descriptionToast';

describe('descriptionAffichable', () => {
  it('garde un texte tel quel', () => {
    expect(descriptionAffichable('Enregistré')).toBe('Enregistré');
  });
  it('lit le message d’un detail 422', () => {
    expect(descriptionAffichable([{ type: 'missing', loc: ['body', 'status'], msg: 'Field required' }])).toBe('Field required');
  });
  it('ne laisse jamais passer un objet', () => {
    expect(descriptionAffichable({ code: 'x' })).toBe('L’action n’a pas abouti.');
  });
});

import { describe, expect, it } from 'vitest';

import { reducer, TOAST_LIMIT } from './use-toast';

describe('pile des messages', () => {
  it('garde trois messages à l’écran : un avertissement ne chasse plus le précédent', () => {
    expect(TOAST_LIMIT).toBe(3);
    let state = { toasts: [] as Parameters<typeof reducer>[0]['toasts'] };
    for (const id of ['1', '2', '3', '4']) {
      state = reducer(state, { type: 'ADD_TOAST', toast: { id, title: `message ${id}`, open: true } });
    }
    expect(state.toasts.map((t) => t.id)).toEqual(['4', '3', '2']);
  });
});

import { describe, expect, it } from 'vitest';
import { runCalendarBatch } from './calendarBatch';

describe('écriture de calendriers en masse', () => {
  it('attend les opérations en cours avant de rendre une erreur', async () => {
    let release!: () => void;
    const pending = new Promise<void>((resolve) => { release = resolve; });
    const error = new Error('conflit');
    let settled = false;
    const batch = runCalendarBatch([async () => { throw error; }, async () => { await pending; return 1; }]);
    void batch.then(() => { settled = true; }, () => { settled = true; });
    await Promise.resolve(); await Promise.resolve();
    expect(settled).toBe(false);
    release();
    await expect(batch).rejects.toMatchObject({ failure: error, completed: 1, total: 2 });
    expect(settled).toBe(true);
  });
  it('garde l’ordre des résultats et limite à cinq les opérations simultanées', async () => {
    let active = 0, maximum = 0;
    const result = await runCalendarBatch(Array.from({ length: 13 }, (_, id) => async () => {
      active++; maximum = Math.max(maximum, active);
      await Promise.resolve(); active--; return id;
    }));
    expect(result).toEqual(Array.from({ length: 13 }, (_, id) => id));
    expect(maximum).toBeLessThanOrEqual(5);
  });
});

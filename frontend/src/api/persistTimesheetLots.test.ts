import { describe, expect, it, vi, beforeEach } from 'vitest';

const post = vi.fn();

vi.mock('./apiClient', () => ({
  apiClient: { post: (...a: unknown[]) => post(...a) },
  default: { post: (...a: unknown[]) => post(...a) },
}));

import { persistTimesheetBatch } from './calendar';

describe('persistTimesheetBatch : relevés importés ensemble', () => {
  beforeEach(() => post.mockReset());

  it('envoie le lot de chaque fichier en plus du lot principal', async () => {
    post.mockResolvedValue({ data: {} });
    await persistTimesheetBatch(2026, 10, [], {
      batchId: 'lot-s43',
      batchIds: ['lot-s39', 'lot-s43'],
      allowPartial: true,
    });
    expect(post.mock.calls[0][1]).toMatchObject({
      batch_id: 'lot-s43',
      batch_ids: ['lot-s39', 'lot-s43'],
    });
  });

  it('un seul lot : batch_ids vide, comme avant', async () => {
    post.mockResolvedValue({ data: {} });
    await persistTimesheetBatch(2026, 10, [], { batchId: 'lot-s43' });
    expect(post.mock.calls[0][1]).toMatchObject({ batch_id: 'lot-s43', batch_ids: [] });
  });
});

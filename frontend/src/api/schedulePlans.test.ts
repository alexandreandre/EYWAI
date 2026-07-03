import { describe, expect, it, vi, beforeEach } from 'vitest';

const post = vi.fn();
const get = vi.fn();
const put = vi.fn();
const del = vi.fn();

vi.mock('./apiClient', () => ({
  default: {
    get: (...a: unknown[]) => get(...a),
    post: (...a: unknown[]) => post(...a),
    put: (...a: unknown[]) => put(...a),
    delete: (...a: unknown[]) => del(...a),
  },
}));

import {
  applySchedulePreset,
  createSchedulePlan,
  generateSchedulePlan,
} from './schedulePlans';

describe('schedulePlans API', () => {
  beforeEach(() => {
    post.mockReset();
    get.mockReset();
    put.mockReset();
    del.mockReset();
  });

  it('applySchedulePreset envoie preset_key au bon endpoint', async () => {
    post.mockResolvedValue({ data: { status: 'success', templates_created: 1, plans_created: 1, plans: [] } });
    await applySchedulePreset('colorplast');
    expect(post).toHaveBeenCalledWith('/api/schedules/presets/apply', { preset_key: 'colorplast' });
  });

  it('generateSchedulePlan transmet plan_id, year et dry_run', async () => {
    post.mockResolvedValue({ data: { status: 'preview', employees: [] } });
    await generateSchedulePlan({ plan_id: 'p1', year: 2026, dry_run: true });
    expect(post).toHaveBeenCalledWith('/api/schedules/generate', {
      plan_id: 'p1',
      year: 2026,
      dry_run: true,
    });
  });

  it('createSchedulePlan poste le payload du plan', async () => {
    post.mockResolvedValue({ data: { id: 'x' } });
    const payload = {
      name: 'Test',
      scope_type: 'company' as const,
      scope_ref: {},
      template_cycle: ['t1', 't2'],
      start_date: '2026-01-01',
      overwrite_mode: 'preserve_manual' as const,
    };
    await createSchedulePlan(payload);
    expect(post).toHaveBeenCalledWith('/api/schedules/plans', payload);
  });
});

import { beforeEach, describe, expect, it, vi } from 'vitest';
vi.mock('@/api/calendar', () => ({ saveCalendar: vi.fn() }));
import { saveCalendar } from '@/api/calendar';
import { restoreCalendarSnapshots } from './calendarBulkUndo';

describe('annuler une action de calendrier', () => {
  beforeEach(() => { vi.mocked(saveCalendar).mockReset(); });
  it('restaure prévu et réel ensemble avec la révision après action et la société d’origine', async () => {
    vi.mocked(saveCalendar).mockResolvedValue({ data: {} } as never);
    await restoreCalendarSnapshots([{ id: 'sal-a', companyId: 'soc-a', expectedRevision: 'apres-action',
      planned: [{ jour: 6, type: 'travail', heures_prevues: 7 }], actual: [{ jour: 6, type: 'travail', heures_faites: 7 }],
    }], 2026, 11);
    expect(saveCalendar).toHaveBeenCalledTimes(1);
    expect(saveCalendar).toHaveBeenCalledWith('sal-a', 2026, 11, {
      expected_revision: 'apres-action', calendrier_prevu: [{ jour: 6, type: 'travail', heures_prevues: 7 }],
      calendrier_reel: [{ jour: 6, type: 'travail', heures_faites: 7 }],
    }, { companyId: 'soc-a' });
  });
  it('conserve un conflit et ne relit pas la dernière révision pour forcer le retour arrière', async () => {
    const conflict = { response: { status: 409, data: { detail: { code: 'calendar_conflict' } } } };
    vi.mocked(saveCalendar).mockRejectedValue(conflict);
    const snapshot = { id: 'sal-a', companyId: 'soc-a', expectedRevision: 'apres-action', planned: [] };
    await expect(restoreCalendarSnapshots([snapshot], 2026, 11)).rejects.toMatchObject({ failure: conflict, completed: 0, total: 1 });
    expect(saveCalendar).toHaveBeenCalledTimes(1);
    expect(snapshot.expectedRevision).toBe('apres-action');
  });
});

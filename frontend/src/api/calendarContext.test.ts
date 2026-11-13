import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios';
import apiClient from './apiClient';
import {
  calculatePayrollEvents,
  getCalendarSnapshot,
  saveCalendar,
  getActualHours,
  getPlannedCalendar,
  updateActualHours,
  updatePlannedCalendar,
} from './calendar';

describe('contexte société des opérations de calendrier', () => {
  const originalAdapter = apiClient.defaults.adapter;
  let activeCompany: string;
  let requests: InternalAxiosRequestConfig[];

  beforeEach(() => {
    activeCompany = 'societe-a';
    requests = [];
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => key === 'activeCompanyId' ? activeCompany : null,
    });
    const adapter: AxiosAdapter = async (config) => {
      requests.push(config);
      return { config, data: {}, status: 200, statusText: 'OK', headers: {} };
    };
    apiClient.defaults.adapter = adapter;
  });

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
    vi.unstubAllGlobals();
  });

  it('garde la société du mois ouvert pour les lectures, écritures et calcul malgré un changement de session', async () => {
    const context = { companyId: activeCompany, expectedRevision: 'revision-a' };
    await getPlannedCalendar('salarie-a', 2026, 11, context);
    activeCompany = 'societe-b';
    await getActualHours('salarie-a', 2026, 11, context);
    await updatePlannedCalendar('salarie-a', 2026, 11, [{ jour: 6, type: 'repos', heures_prevues: 0 }], context);
    await updateActualHours('salarie-a', 2026, 11, [{ jour: 6, type: 'repos', heures_faites: 0 }], context);
    await calculatePayrollEvents('salarie-a', 2026, 11, context);

    expect(requests).toHaveLength(5);
    expect(requests.map((r) => r.headers.get('X-Active-Company'))).toEqual(Array(5).fill('societe-a'));
    expect(requests.every((r) => r.url?.startsWith('/api/employees/salarie-a/'))).toBe(true);
    expect(requests.slice(2).map((r) => JSON.parse(r.data))).toEqual([
      { year: 2026, month: 11, expected_revision: 'revision-a', calendrier_prevu: [{ jour: 6, type: 'repos', heures_prevues: 0 }] },
      { year: 2026, month: 11, expected_revision: 'revision-a', calendrier_reel: [{ jour: 6, type: 'repos', heures_faites: 0 }] },
      { year: 2026, month: 11 },
    ]);
  });

  it('conserve le comportement existant des appels sans contexte explicite', async () => {
    activeCompany = 'societe-b';
    await getActualHours('salarie-b', 2026, 12);
    expect(requests[0].headers.get('X-Active-Company')).toBe('societe-b');
    expect(requests[0].params).toEqual({ year: 2026, month: 12 });
  });

  it('conserve la société au retry de lecture après une erreur transitoire', async () => {
    apiClient.defaults.adapter = async (config) => {
      requests.push(config);
      if (requests.length === 1) {
        activeCompany = 'societe-b';
        throw new AxiosError('Indisponibilité simulée', 'ERR_BAD_RESPONSE', config, undefined, {
          config, data: {}, status: 503, statusText: 'Unavailable', headers: {},
        });
      }
      return { config, data: {}, status: 200, statusText: 'OK', headers: {} };
    };
    await getPlannedCalendar('salarie-a', 2026, 11, { companyId: 'societe-a' });
    expect(requests.map((r) => r.headers.get('X-Active-Company'))).toEqual(['societe-a', 'societe-a']);
  });
  it('envoie prévu et réel avec la révision lue dans un seul enregistrement réservé', async () => {
    const context = { companyId: activeCompany };
    await getCalendarSnapshot('salarie-a', 2026, 11, context);
    activeCompany = 'societe-b';
    await saveCalendar('salarie-a', 2026, 11, {
      expected_revision: null, calendrier_prevu: [], calendrier_reel: [], recalculate_payroll: true,
    }, context);
    expect(requests.map((r) => r.headers.get('X-Active-Company'))).toEqual(['societe-a', 'societe-a']);
    expect(requests[1].url).toBe('/api/employees/salarie-a/calendar-save');
    expect(JSON.parse(requests[1].data)).toEqual({ year: 2026, month: 11, expected_revision: null,
      calendrier_prevu: [], calendrier_reel: [], recalculate_payroll: true });
  });

  it('refuse une écriture sans révision avant toute requête réseau', async () => {
    await expect(updatePlannedCalendar('salarie-a', 2026, 11, [])).rejects.toThrow('Rechargez');
    await expect(updateActualHours('salarie-a', 2026, 11, [])).rejects.toThrow('Rechargez');
    expect(requests).toEqual([]);
  });

  it('ne rejoue pas un enregistrement dont la réponse est incertaine', async () => {
    apiClient.defaults.adapter = async (config) => {
      requests.push(config);
      throw new AxiosError('Réponse perdue simulée', 'ERR_BAD_RESPONSE', config, undefined, {
        config, data: {}, status: 503, statusText: 'Unavailable', headers: {},
      });
    };
    await expect(saveCalendar('salarie-a', 2026, 11, { expected_revision: 'revision-a', calendrier_prevu: [] }))
      .rejects.toMatchObject({ response: { status: 503 } });
    expect(requests).toHaveLength(1);
  });

});

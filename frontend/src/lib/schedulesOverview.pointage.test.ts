import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/api/calendar', () => ({
  getPlannedCalendar: vi.fn(),
  getActualHours: vi.fn(),
}));
vi.mock('@/api/absences', () => ({
  getAbsencesForEmployee: vi.fn(),
}));

import * as calendarApi from '@/api/calendar';
import { getAbsencesForEmployee } from '@/api/absences';
import { applyDayPatchToRow, fetchAllEmployeesOverview } from './schedulesOverview';

const SALARIE = { id: 'e1', first_name: 'Prénom', last_name: 'Nom', statut: 'Non-Cadre' };

function septembrePrevu() {
  const jours = [];
  for (let jour = 1; jour <= 30; jour++) {
    const dimancheOuSamedi = [0, 6].includes(new Date(2026, 8, jour).getDay());
    jours.push(
      dimancheOuSamedi
        ? { jour, type: 'weekend', heures_prevues: 0 }
        : { jour, type: 'travail', heures_prevues: 8 }
    );
  }
  return jours;
}

/** Le réel de chaque mois demandé ; `'erreur'` fait échouer la lecture. */
function reels(parMois: Record<number, unknown[] | 'erreur'>) {
  vi.mocked(calendarApi.getPlannedCalendar).mockResolvedValue({
    data: { calendrier_prevu: septembrePrevu() },
  } as never);
  vi.mocked(calendarApi.getActualHours).mockImplementation(async (_id, _annee, mois) => {
    const reel = parMois[mois as number] ?? [];
    if (reel === 'erreur') throw new Error('lecture impossible');
    return { data: { calendrier_reel: reel } } as never;
  });
}

async function ligneDeSeptembre() {
  const [ligne] = await fetchAllEmployeesOverview([SALARIE], 2026, 9);
  return ligne;
}

describe('Plannings : un salarié qui ne pointe pas', () => {
  beforeEach(() => {
    vi.mocked(getAbsencesForEmployee).mockResolvedValue({ data: [] } as never);
  });

  it("n'a rien à saisir quand aucune heure n'est pointée ni ce mois ni le précédent", async () => {
    reels({ 8: [], 9: [] });

    const ligne = await ligneDeSeptembre();

    expect(ligne.loadError).toBe(false);
    expect(ligne.rowStatus).toBe('saisi');
    expect(calendarApi.getActualHours).toHaveBeenCalledWith('e1', 2026, 8);
  });

  it('reste à saisir quand il a pointé le mois précédent (import du mois oublié)', async () => {
    reels({ 8: [{ jour: 31, heures_faites: 8.5 }], 9: [] });

    expect((await ligneDeSeptembre()).rowStatus).toBe('a_saisir');
  });

  it('reste à saisir quand le mois précédent ne se lit pas', async () => {
    reels({ 8: 'erreur', 9: [] });

    const ligne = await ligneDeSeptembre();

    expect(ligne.loadError).toBe(false);
    expect(ligne.rowStatus).toBe('a_saisir');
  });

  it('une saisie dans le tableau suit la même règle', async () => {
    reels({ 8: [], 9: [] });
    const ligne = await ligneDeSeptembre();

    // Un 0 h saisi un jour travaillé : à saisir.
    expect(applyDayPatchToRow(ligne, 1, { heures_faites: 0 }, 2026, 9).rowStatus).toBe(
      'a_saisir'
    );
    // Une première heure pointée : le salarié pointe, les autres jours manquent.
    expect(applyDayPatchToRow(ligne, 1, { heures_faites: 8 }, 2026, 9).rowStatus).toBe(
      'a_saisir'
    );
  });
});

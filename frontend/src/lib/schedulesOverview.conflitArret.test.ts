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
import { fetchAllEmployeesOverview } from './schedulesOverview';
import {
  ecartAffiche,
  messageFiltreSansCalendrier,
  phraseHeuresSurArret,
  resumeHeuresSurArret,
} from './calendrierPilotage';

const SALARIE = { id: 'e1', first_name: 'Élodie', last_name: 'Vasseur', statut: 'Non-Cadre' };

function prevuOctobre() {
  const jours = [];
  for (let jour = 1; jour <= 31; jour++) {
    const finDeSemaine = [0, 6].includes(new Date(2026, 9, jour).getDay());
    jours.push(
      finDeSemaine
        ? { jour, type: 'weekend', heures_prevues: 0 }
        : { jour, type: 'travail', heures_prevues: 7 },
    );
  }
  return jours;
}

function reelComplet() {
  return prevuOctobre()
    .filter((p) => p.type === 'travail')
    .map((p) => ({ jour: p.jour, type: 'travail', heures_faites: 7 }));
}

describe('Calendrier : heures saisies un jour d’arrêt', () => {
  beforeEach(() => {
    vi.mocked(getAbsencesForEmployee).mockResolvedValue({ data: [] } as never);
    vi.mocked(calendarApi.getPlannedCalendar).mockResolvedValue({
      data: { calendrier_prevu: prevuOctobre() },
    } as never);
  });

  it('garde les jours en conflit renvoyés par l’API et ne déclare pas le salarié prêt', async () => {
    vi.mocked(calendarApi.getActualHours).mockResolvedValue({
      data: { calendrier_reel: reelComplet(), jours_en_conflit: [19, 20] },
    } as never);

    const [ligne] = await fetchAllEmployeesOverview([SALARIE], 2026, 10);

    expect(ligne.joursHeuresSurArret).toEqual([19, 20]);
    expect(ligne.rowStatus).toBe('saisi_avec_ecart');
  });

  it('sans conflit, le salarié complet reste prêt', async () => {
    vi.mocked(calendarApi.getActualHours).mockResolvedValue({
      data: { calendrier_reel: reelComplet(), jours_en_conflit: [] },
    } as never);

    const [ligne] = await fetchAllEmployeesOverview([SALARIE], 2026, 10);

    expect(ligne.joursHeuresSurArret).toEqual([]);
    expect(ligne.rowStatus).toBe('saisi');
  });
});

describe('resumeHeuresSurArret / phraseHeuresSurArret', () => {
  const rows = [
    { employee: { id: 'e1', first_name: 'Élodie', last_name: 'Vasseur' }, joursHeuresSurArret: [19, 20] },
    { employee: { id: 'e2', first_name: 'Léa', last_name: 'Fontaine' }, joursHeuresSurArret: [] },
  ];

  it('compte les jours et nomme les salariés concernés', () => {
    const r = resumeHeuresSurArret(rows as never);
    expect(r.totalJours).toBe(2);
    expect(r.salaries).toEqual([{ id: 'e1', nom: 'Élodie Vasseur', jours: [19, 20] }]);
  });

  it('dit combien de jours portent des heures pendant un arrêt', () => {
    expect(phraseHeuresSurArret(resumeHeuresSurArret(rows as never))).toBe(
      '2 jours portent des heures pendant un arrêt ou une absence (Élodie Vasseur) : la génération de la paie sera refusée tant qu’ils ne sont pas corrigés.',
    );
  });

  it('rien à dire sans conflit', () => {
    expect(phraseHeuresSurArret(resumeHeuresSurArret([rows[1]] as never))).toBeNull();
  });
});

describe('messageFiltreSansCalendrier', () => {
  it('sous « À saisir », dit qu’il ne reste plus de calendrier à saisir', () => {
    expect(messageFiltreSansCalendrier('a_saisir', 4)).toEqual({
      titre: 'Plus aucun calendrier à saisir',
      detail: 'Tous les calendriers de ce mois sont saisis.',
    });
  });

  it('sous un autre filtre, garde le message générique', () => {
    expect(messageFiltreSansCalendrier('saisi_avec_ecart', 4).titre).toBe(
      'Aucun employé ne correspond à vos filtres',
    );
    expect(messageFiltreSansCalendrier('all', 4).titre).toBe(
      'Aucun employé ne correspond à vos filtres',
    );
  });
});

describe('ecartAffiche', () => {
  it('n’affiche pas d’écart tant que le calendrier n’est pas complet', () => {
    expect(ecartAffiche({ rowStatus: 'a_saisir', isForfaitJour: false, ecart: -105 })).toBeNull();
  });

  it('affiche l’écart signé en heures, ou en jours au forfait', () => {
    expect(ecartAffiche({ rowStatus: 'saisi', isForfaitJour: false, ecart: 1.5 })).toBe('+1.5 h');
    expect(ecartAffiche({ rowStatus: 'saisi_avec_ecart', isForfaitJour: false, ecart: -2 })).toBe('-2.0 h');
    expect(ecartAffiche({ rowStatus: 'saisi', isForfaitJour: true, ecart: 1 })).toBe('+1 j');
  });
});

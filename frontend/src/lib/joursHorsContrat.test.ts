import { describe, expect, it } from 'vitest';
import type { ActualHoursData, PlannedEventData } from '@/api/calendar';
import { computeEmployeeRowStatus, joursASaisir } from './calendarStats';
import {
  estAvantLEntree,
  libelleAvantEntree,
  phraseAvantBascule,
  premierJourDansLeMois,
  premierJourDuContratDansLeMois,
} from './joursHorsContrat';
import { bornesDuSalarie } from './schedulesOverview';
import { alerteDeSaisie } from './alerteDeSaisie';

/** Octobre 2026 : prévu 7 h chaque jour ouvré, rien au réel (rien n'a été saisi). */
function octobreVide(): { planned: PlannedEventData[]; actual: ActualHoursData[] } {
  const planned: PlannedEventData[] = [];
  const actual: ActualHoursData[] = [];
  for (let jour = 1; jour <= 31; jour++) {
    const dow = new Date(2026, 9, jour).getDay();
    const weekend = dow === 0 || dow === 6;
    planned.push({ jour, type: weekend ? 'weekend' : 'travail', heures_prevues: weekend ? 0 : null });
    actual.push({ jour, type: weekend ? 'weekend' : 'travail', heures_faites: null });
  }
  return { planned, actual };
}

describe('premierJourDansLeMois', () => {
  it('une date dans le mois donne son jour', () => {
    expect(premierJourDansLeMois('2026-10-05', 2026, 10)).toBe(5);
  });
  it('une date avant le mois (ou le 1er) n’exclut rien', () => {
    expect(premierJourDansLeMois('2026-09-12', 2026, 10)).toBeNull();
    expect(premierJourDansLeMois('2026-10-01', 2026, 10)).toBeNull();
    expect(premierJourDansLeMois(null, 2026, 10)).toBeNull();
  });
  it('une date après le mois exclut tout le mois', () => {
    expect(premierJourDansLeMois('2026-11-02', 2026, 10)).toBe(32);
  });
});

describe('jours avant l’entrée (salarié entré le 05/10)', () => {
  const entre = { hire_date: '2026-10-05' };

  it('le premier jour du contrat est le 5', () => {
    expect(premierJourDuContratDansLeMois(entre, 2026, 10)).toBe(5);
    expect(estAvantLEntree(4, 5)).toBe(true);
    expect(estAvantLEntree(5, 5)).toBe(false);
    expect(estAvantLEntree(4, null)).toBe(false);
  });

  it('les jours d’avant ne sont plus « à saisir »', () => {
    const { planned, actual } = octobreVide();
    const { bornes } = bornesDuSalarie(
      { id: 's', first_name: '', last_name: '', ...entre },
      2026,
      10,
      false,
    );
    expect(bornes.premierJour).toBe(5);
    const jours = joursASaisir(planned, actual, 2026, 10, false, true, bornes).map((j) => j.jour);
    expect(jours).not.toContain(1);
    expect(jours).not.toContain(2);
    expect(jours[0]).toBe(5);
  });

  it('un mois rempli depuis l’entrée est « saisi »', () => {
    const { planned, actual } = octobreVide();
    for (const p of planned) if (p.type === 'travail') p.heures_prevues = 7;
    for (const a of actual) if (a.type === 'travail' && a.jour >= 5) a.heures_faites = 7;
    expect(computeEmployeeRowStatus(planned, actual, 2026, 10, false, true, {})).toBe('a_saisir');
    expect(computeEmployeeRowStatus(planned, actual, 2026, 10, false, true, { premierJour: 5 })).toBe(
      'saisi',
    );
  });

  it('l’infobulle de la case dit pourquoi elle est grise', () => {
    expect(libelleAvantEntree(5, 10)).toBe('Avant l’entrée le 05/10 : hors contrat, rien à saisir.');
    expect(libelleAvantEntree(32, 10)).toBe('Entrée après ce mois : hors contrat, rien à saisir.');
  });
});

describe('jours payés par l’ancien logiciel (bascule)', () => {
  it('avant le début de la première paie Martine, rien n’est compté', () => {
    const { bornes, premierJourMartine } = bornesDuSalarie(
      { id: 's', first_name: '', last_name: '' },
      2026,
      9,
      false,
      { debutMartine: '2026-09-21' },
    );
    expect(premierJourMartine).toBe(21);
    expect(bornes.premierJour).toBe(21);
  });

  it('l’entrée la plus tardive l’emporte', () => {
    const { bornes } = bornesDuSalarie(
      { id: 's', first_name: '', last_name: '', hire_date: '2026-09-25' },
      2026,
      9,
      false,
      { debutMartine: '2026-09-21' },
    );
    expect(bornes.premierJour).toBe(25);
  });

  it('un mois après la bascule est jugé en entier', () => {
    const { bornes } = bornesDuSalarie({ id: 's', first_name: '', last_name: '' }, 2026, 10, false, {
      debutMartine: '2026-09-21',
    });
    expect(bornes.premierJour ?? null).toBeNull();
  });

  it('la phrase de l’écran le dit', () => {
    expect(phraseAvantBascule('2026-09-21', 'Quadra')).toBe(
      'Jours avant le 21/09/2026 : payés par l’ancien logiciel (Quadra), non comptés.',
    );
    expect(phraseAvantBascule('2026-09-21', null)).toBe(
      'Jours avant le 21/09/2026 : payés par l’ancien logiciel, non comptés.',
    );
  });

  it('l’alerte d’un salarié rappelle ces bornes', () => {
    const alerte = alerteDeSaisie(
      {
        rowStatus: 'a_saisir',
        joursASaisir: [{ jour: 22, motif: 'prevu_sans_reel' }],
        premierJourContrat: null,
        premierJourMartine: 21,
        debutMartine: '2026-09-21',
      },
      2026,
      9,
    );
    expect(alerte?.detail).toContain('Jours avant le 21/09/2026 : payés par l’ancien logiciel, non comptés.');
    const entree = alerteDeSaisie(
      {
        rowStatus: 'a_saisir',
        joursASaisir: [{ jour: 6, motif: 'prevu_sans_reel' }],
        premierJourContrat: 5,
      },
      2026,
      10,
    );
    expect(entree?.detail).toContain('Rien n’est attendu avant l’entrée le 05/10.');
  });
});

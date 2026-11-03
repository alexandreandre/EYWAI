import { describe, expect, it } from 'vitest';
import {
  TYPE_ABSENT_A_TYPER,
  estAbsentATyper,
  joursAbsentsATyper,
  phraseAbsentsATyper,
  aDesAbsentsATyper,
  correspondAuFiltreSaisie,
  phraseBandeauAbsents,
  resumeAbsentsATyper,
} from './absentATyper';
import { computeGlobalKpis, type EmployeeCalendarOverviewRow } from './schedulesOverview';

describe('jours « absent, type à donner »', () => {
  it('repère les jours du prévu marqués absents', () => {
    const prevu = [
      { jour: 8, type: 'travail', heures_prevues: 7 },
      { jour: 9, type: TYPE_ABSENT_A_TYPER, heures_prevues: 7 },
      { jour: 10, type: 'conges_payes', heures_prevues: 0 },
      { jour: 11, type: TYPE_ABSENT_A_TYPER, heures_prevues: 7 },
    ];
    expect(joursAbsentsATyper(prevu)).toEqual([9, 11]);
    expect(estAbsentATyper(prevu[1])).toBe(true);
    expect(estAbsentATyper(prevu[2])).toBe(false);
  });

  it('dit les jours en clair', () => {
    expect(phraseAbsentsATyper([9])).toBe('1 jour absent sans type (le 9)');
    expect(phraseAbsentsATyper([9, 11])).toBe('2 jours absents sans type (les 9 et 11)');
  });

  it('un salarié avec un jour absent sans type n’est pas prêt pour la paie', () => {
    const ligne = {
      employee: { id: 'e1' },
      planned: [],
      actual: [],
      heuresPrevues: 0,
      heuresFaites: 0,
      ecart: 0,
      rowStatus: 'saisi',
      absenceConflictDays: [],
      joursAbsentsATyper: [9],
      loadError: false,
      isForfaitJour: false,
    } as unknown as EmployeeCalendarOverviewRow;
    const kpis = computeGlobalKpis([ligne]);
    expect(kpis.prets).toBe(0);
    expect(kpis.avecAbsentsATyper).toBe(1);
  });
});

describe('page Calendrier : filtre « À saisir » et bandeau « tout est prêt »', () => {
  const ligne = (rowStatus: string, absents: number[] = []) => ({ rowStatus, joursAbsentsATyper: absents });

  it('le filtre « À saisir » garde un salarié dont un jour est absent sans type', () => {
    expect(correspondAuFiltreSaisie(ligne('saisi', [9]), 'a_saisir')).toBe(true);
    expect(correspondAuFiltreSaisie(ligne('saisi'), 'a_saisir')).toBe(false);
    expect(correspondAuFiltreSaisie(ligne('a_saisir'), 'a_saisir')).toBe(true);
    expect(correspondAuFiltreSaisie(ligne('saisi', [9]), 'saisi')).toBe(true);
    expect(correspondAuFiltreSaisie(ligne('saisi', [9]), 'all')).toBe(true);
  });

  it('un jour absent sans type empêche de dire que tout est prêt', () => {
    expect(aDesAbsentsATyper(ligne('saisi', [9]))).toBe(true);
    expect(aDesAbsentsATyper(ligne('saisi'))).toBe(false);
  });
});

describe('bandeau de la page Calendrier', () => {
  it('nomme les salariés et dit que la paie est bloquée', () => {
    const lignes = [
      { employee: { id: 'e1', first_name: 'Élodie', last_name: 'Essai' }, joursAbsentsATyper: [14] },
      { employee: { id: 'e2', first_name: 'Mathis', last_name: 'Essai' }, joursAbsentsATyper: [] },
    ];
    const resume = resumeAbsentsATyper(lignes);
    expect(resume).toEqual([{ id: 'e1', nom: 'Élodie Essai', jours: [14] }]);
    expect(phraseBandeauAbsents(resume)).toBe(
      '1 jour est marqué « absent » sans type (Élodie Essai) : donnez-lui son type dans le calendrier. La paie de ce salarié est refusée, sans forçage possible, jusque-là.'
    );
    expect(phraseBandeauAbsents([])).toBeNull();
  });
});

import { describe, expect, it } from 'vitest';
import type { SeniorityImportRosterEmployee } from '@/api/adminImport';
import { associateSeniorityRow, isSavableSeniorityRow, type EditableSeniorityRow } from './seniorityImportReview';

const row: EditableSeniorityRow = {
  row_index: 5, raw_identity: 'Alix EXEMPLE', seniority_date_raw: '03/09/2018',
  seniority_date: '2018-09-03', employee_id: 'sal-a', matched_name: 'Alix EXEMPLE',
  match_confidence: 'high', match_method: 'matricule', review_status: 'ok',
  warnings: [], current_seniority_date: '2019-01-07', current_hire_date: '2020-01-06',
  unchanged: false, raw_row: {}, manuallyConfirmed: true,
};
const roster: SeniorityImportRosterEmployee[] = [
  { id: 'sal-a', first_name: 'Alix', last_name: 'EXEMPLE', current_seniority_date: '2019-01-07', current_hire_date: '2020-01-06' },
  { id: 'sal-b', first_name: 'Camille', last_name: 'EXEMPLE', current_seniority_date: '2018-09-03', current_hire_date: '2021-02-01' },
];

describe('revue des dates d’ancienneté', () => {
  it('décocher une ligne prête l’exclut du payload', () => {
    expect(isSavableSeniorityRow(row)).toBe(true);
    expect([row, { ...row, employee_id: 'sal-b', manuallyConfirmed: false }].filter(isSavableSeniorityRow)).toEqual([row]);
    expect(isSavableSeniorityRow({ ...row, manuallyConfirmed: false })).toBe(false);
  });

  it('une proposition à vérifier exige une confirmation explicite', () => {
    expect(isSavableSeniorityRow({ ...row, review_status: 'warning', manuallyConfirmed: false })).toBe(false);
    expect(isSavableSeniorityRow({ ...row, review_status: 'warning', manuallyConfirmed: true })).toBe(true);
  });

  it('une ligne sans salarié, sans date ou identique ne part pas à l’enregistrement', () => {
    for (const changes of [{ employee_id: null }, { seniority_date: null }, { unchanged: true }, { current_seniority_date: row.seniority_date }]) {
      expect(isSavableSeniorityRow({ ...row, ...changes })).toBe(false);
    }
  });

  it('changer de salarié remplace les dates actuelles et recalcule identique', () => {
    const associated = associateSeniorityRow(row, 'sal-b', roster);
    expect(associated.employee_id).toBe('sal-b');
    expect(associated.current_seniority_date).toBe('2018-09-03');
    expect(associated.current_hire_date).toBe('2021-02-01');
    expect(associated.unchanged).toBe(true);
    expect(associated.manuallyConfirmed).toBe(false);
    expect(isSavableSeniorityRow(associated)).toBe(false);
  });

  it('réassocier une ancienne ligne identique redemande une confirmation pour la différence', () => {
    const associated = associateSeniorityRow({ ...row, employee_id: 'sal-b', unchanged: true }, 'sal-a', roster);
    expect(associated.unchanged).toBe(false);
    expect(associated.manuallyConfirmed).toBe(false);
    expect(isSavableSeniorityRow(associated)).toBe(false);
    expect(isSavableSeniorityRow({ ...associated, manuallyConfirmed: true })).toBe(true);
  });

  it('retirer ou choisir un salarié inconnu efface les dates du précédent', () => {
    for (const id of [null, 'inconnu']) {
      const associated = associateSeniorityRow(row, id, roster);
      expect(associated.employee_id).toBeNull();
      expect(associated.current_seniority_date).toBeNull();
      expect(associated.current_hire_date).toBeNull();
      expect(isSavableSeniorityRow(associated)).toBe(false);
    }
  });
});

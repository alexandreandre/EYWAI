import { describe, expect, it } from 'vitest';
import {
  purgeEmployeesProgressPercent,
  PURGE_EMPLOYEE_STEPS,
} from '@/lib/purgeEmployeesProgress';

describe('purgeEmployeesProgressPercent', () => {
  it('calcule la progression par salarié et par étape', () => {
    expect(purgeEmployeesProgressPercent(2, 1, 'preparation')).toBe(10);
    expect(purgeEmployeesProgressPercent(2, 1, 'storage')).toBe(20);
    expect(purgeEmployeesProgressPercent(2, 1, 'finalize')).toBe(50);
    expect(purgeEmployeesProgressPercent(2, 1, undefined, true)).toBe(50);
    expect(purgeEmployeesProgressPercent(2, 2, undefined, true)).toBe(100);
  });

  it('retourne 100 si aucun salarié', () => {
    expect(purgeEmployeesProgressPercent(0, 0)).toBe(100);
  });

  it('couvre toutes les étapes connues', () => {
    expect(PURGE_EMPLOYEE_STEPS).toHaveLength(5);
  });
});

import { describe, expect, it } from 'vitest';
import type { PreflightAnomaly } from '@/api/payrollPreflight';
import {
  PREFLIGHT_ANOMALY_TYPE_LABELS,
  PREFLIGHT_ANOMALY_TYPE_ORDER,
  verifyPathForAnomaly,
} from './preflightLabels';

const anomalie = (type: PreflightAnomaly['type']): PreflightAnomaly => ({
  id: 'e1:' + type,
  employee_id: 'e1',
  employee_name: 'Michel BUGNY',
  type,
  severity: 'a_verifier',
  status: 'a_traiter',
  is_forfait_jour: false,
  detail_jours: [],
  conflict_days: [],
});

describe('fenetre_modifiee', () => {
  it('a un libellé, une place dans l’ordre et renvoie au lancement de paie', () => {
    expect(PREFLIGHT_ANOMALY_TYPE_LABELS.fenetre_modifiee).toBe('Fenêtre modifiée');
    expect(PREFLIGHT_ANOMALY_TYPE_ORDER).toContain('fenetre_modifiee');
    expect(verifyPathForAnomaly(anomalie('fenetre_modifiee'))).toBe('/payroll');
  });
});

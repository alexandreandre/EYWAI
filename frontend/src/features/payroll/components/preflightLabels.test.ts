import { describe, expect, it } from 'vitest';
import type { PreflightAnomaly } from '@/api/payrollPreflight';
import { isPayrollFocusAllowed } from '@/lib/payrollFocus';
import {
  correctionPathForType,
  PREFLIGHT_ANOMALY_TYPE_LABELS,
  PREFLIGHT_ANOMALY_TYPE_ORDER,
  verifyPathForAnomaly,
} from './preflightLabels';

const anomalie = (type: PreflightAnomaly['type']): PreflightAnomaly => ({
  id: 'e1:' + type,
  employee_id: 'e1',
  employee_name: 'Michel DUMAREL',
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

describe('fiche_dsn', () => {
  it('a un libellé, passe en tête et ouvre la modification de la fiche', () => {
    expect(PREFLIGHT_ANOMALY_TYPE_LABELS.fiche_dsn).toBe('Fiche à compléter (DSN)');
    expect(PREFLIGHT_ANOMALY_TYPE_ORDER[0]).toBe('fiche_dsn');
    expect(verifyPathForAnomaly(anomalie('fiche_dsn'))).toBe('/employees/e1?modifier=fiche');
  });
});

describe('liens des anomalies en mode paie', () => {
  it('chaque lien d’action mène à une page permise par le mode paie', () => {
    for (const type of PREFLIGHT_ANOMALY_TYPE_ORDER) {
      const chemin = verifyPathForAnomaly(anomalie(type));
      expect(isPayrollFocusAllowed(chemin), `${type} → ${chemin}`).toBe(true);
    }
  });

  it('un pointage à corriger mène au calendrier du salarié, pas à la badgeuse', () => {
    expect(verifyPathForAnomaly(anomalie('pointage'))).toBe('/schedules?employee=e1');
  });

  it('le lien déprécié suit la même règle', () => {
    expect(isPayrollFocusAllowed(correctionPathForType('pointage'))).toBe(true);
  });
});

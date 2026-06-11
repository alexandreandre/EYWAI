import { describe, expect, it } from 'vitest';
import type { PreflightAnomaly } from '@/api/payrollPreflight';
import {
  countOpenByType,
  formatEcartValue,
  groupAnomaliesByEmployee,
  PREFLIGHT_RESOLUTION_MOTIF_LABELS,
} from '@/features/payroll/components/review/preflightLabels';

function anomaly(partial: Partial<PreflightAnomaly> & Pick<PreflightAnomaly, 'id' | 'type'>): PreflightAnomaly {
  return {
    employee_id: 'emp-1',
    employee_name: 'Jean Dupont',
    severity: 'bloquant',
    status: 'a_traiter',
    detail_jours: [],
    conflict_days: [],
    is_forfait_jour: false,
    ...partial,
  };
}

describe('preflightLabels', () => {
  it('formate un écart heures', () => {
    expect(
      formatEcartValue(
        anomaly({
          id: '1:ecart_heures',
          type: 'ecart_heures',
          ecart: 3.5,
        }),
      ),
    ).toBe('+3.5 h');
  });

  it('formate un écart forfait en jours', () => {
    expect(
      formatEcartValue(
        anomaly({
          id: '1:ecart_heures',
          type: 'ecart_heures',
          ecart: -1,
          is_forfait_jour: true,
        }),
      ),
    ).toBe('-1.0 j');
  });

  it('regroupe par employé', () => {
    const grouped = groupAnomaliesByEmployee([
      anomaly({ id: '1:a', type: 'ecart_heures' }),
      anomaly({ id: '1:b', type: 'pointage' }),
      anomaly({ id: '2:c', type: 'ecart_heures', employee_id: 'emp-2' }),
    ]);
    expect(grouped.get('emp-1')).toHaveLength(2);
    expect(grouped.get('emp-2')).toHaveLength(1);
  });

  it('compte les anomalies ouvertes par type', () => {
    const rows = [
      anomaly({ id: '1:a', type: 'ecart_heures', status: 'a_traiter' }),
      anomaly({ id: '1:b', type: 'ecart_heures', status: 'justifie' }),
      anomaly({ id: '1:c', type: 'pointage', status: 'a_traiter' }),
    ];
    expect(countOpenByType(rows, 'ecart_heures')).toBe(1);
    expect(countOpenByType(rows, 'pointage')).toBe(1);
  });

  it('expose le motif directeur de site', () => {
    expect(PREFLIGHT_RESOLUTION_MOTIF_LABELS.directeur_site).toContain('directeur de site');
  });
});

describe('JustifyAnomalyDialog validation', () => {
  it('exige un commentaire pour le motif autre', () => {
    const requiresComment = (motif: keyof typeof PREFLIGHT_RESOLUTION_MOTIF_LABELS, commentaire: string) =>
      motif !== 'autre' || commentaire.trim().length > 0;

    expect(requiresComment('directeur_site', '')).toBe(true);
    expect(requiresComment('autre', '')).toBe(false);
    expect(requiresComment('autre', 'Précision')).toBe(true);
  });
});

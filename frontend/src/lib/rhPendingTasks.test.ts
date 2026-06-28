import { describe, expect, it } from 'vitest';

import { buildRhPendingTasks, sumRhPendingActions } from './rhPendingTasks';

const emptyInput = {
  pendingAbsences: 0,
  pendingExpenses: 0,
  obsoleteRates: 0,
  expiringContracts: 0,
  endOfTrialPeriods: 0,
  residenceExpire: 0,
  residenceRenew: 0,
  residenceMissing: 0,
  medicalEnabled: false,
  medicalOverdue: 0,
  medicalDue30: 0,
  ribTotal: 0,
  annualReviewsUpcoming: 0,
  recruitmentEnabled: false,
  recruitmentPending: 0,
  schedulesDue: 0,
  workMedalsAwaiting: 0,
  rttClosable: 0,
  modulationAlerts: 0,
  cetPending: 0,
  incompleteProfiles: 0,
  pendingSignatures: 0,
};

describe('buildRhPendingTasks', () => {
  it('agrège les actions en attente sur plusieurs modules', () => {
    const items = buildRhPendingTasks({
      ...emptyInput,
      residenceExpire: 1,
      residenceRenew: 1,
      pendingAbsences: 3,
      schedulesDue: 2,
      cetPending: 1,
    });

    expect(items.map((i) => i.id)).toEqual(['leaves', 'residence', 'schedules', 'cet']);
    expect(sumRhPendingActions(items)).toBe(8);
  });

  it('fusionne absences et clôtures RTT', () => {
    const items = buildRhPendingTasks({
      ...emptyInput,
      pendingAbsences: 2,
      rttClosable: 1,
    });

    expect(items).toHaveLength(1);
    expect(items[0].id).toBe('leaves');
    expect(items[0].count).toBe(3);
  });
});

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

import { filterTasksToPayrollFocus } from './rhPendingTasks';
import type { RhPendingTaskItem } from './rhPendingTasks';
import { CalendarCheck } from 'lucide-react';

const task = (id: string, href: string): RhPendingTaskItem =>
  ({ id, label: id, count: 1, href, icon: CalendarCheck, hint: '' }) as RhPendingTaskItem;

describe('filterTasksToPayrollFocus', () => {
  it('garde les tâches dont la destination est dans le périmètre', () => {
    const kept = filterTasksToPayrollFocus([
      task('leaves', '/leaves'),
      task('expenses', '/expenses'),
      task('contracts', '/employees?alert=deadlines'),
      task('rates', '/rates'),
    ]);
    expect(kept.map((t) => t.id)).toEqual(['leaves', 'expenses', 'contracts', 'rates']);
  });

  it('retire les tâches menant vers un écran retiré', () => {
    const kept = filterTasksToPayrollFocus([
      task('medical', '/medical-follow-up'),
      task('residence', '/residence-permits'),
      task('reviews', '/annual-reviews?focus=upcoming'),
      task('recruitment', '/recruitment'),
      task('onboarding', '/onboarding'),
      task('company', '/company'),
    ]);
    expect(kept).toEqual([]);
  });

  it('ne modifie pas la liste reçue', () => {
    const input = [task('leaves', '/leaves'), task('medical', '/medical-follow-up')];
    filterTasksToPayrollFocus(input);
    expect(input).toHaveLength(2);
  });
});

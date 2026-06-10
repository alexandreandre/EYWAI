import { describe, expect, it } from 'vitest';

import type { Notification } from '@/api/notifications';

import {
  getNotificationHref,
  getNotificationTypeLabel,
  isPayslipAlertNotification,
  isUnreadDocumentAlertNotification,
  resolveNotificationNavContext,
} from './notificationUtils';

describe('notificationUtils — documents et bulletins', () => {
  it('labels nouveau_document in French', () => {
    expect(getNotificationTypeLabel('nouveau_document')).toBe('Nouveau document');
  });

  it('labels nouveau_bulletin in French', () => {
    expect(getNotificationTypeLabel('nouveau_bulletin')).toBe('Nouveau bulletin');
  });

  it('links employee documents to documents page', () => {
    expect(getNotificationHref('nouveau_document', 'employee')).toBe('/employee/documents');
  });

  it('links employee bulletins to payslips page', () => {
    expect(getNotificationHref('nouveau_bulletin', 'employee')).toBe('/payslips');
  });

  it('links legacy bulletin message on nouveau_document to payslips', () => {
    expect(
      getNotificationHref(
        'nouveau_document',
        'employee',
        'Un nouveau document est disponible : « Bulletin de paie — mars 2026 ».',
      ),
    ).toBe('/payslips');
  });

  it('links RH bulletins to payroll page', () => {
    expect(getNotificationHref('nouveau_bulletin', 'rh')).toBe('/payroll');
  });

  it('detects payslip alert from type or legacy message', () => {
    expect(
      isPayslipAlertNotification({
        type: 'nouveau_bulletin',
        message: 'Votre bulletin de paie est disponible.',
      }),
    ).toBe(true);
    expect(
      isPayslipAlertNotification({
        type: 'nouveau_document',
        message: 'Un nouveau document : « Bulletin de paie — janvier 2026 ».',
      }),
    ).toBe(true);
    expect(
      isPayslipAlertNotification({
        type: 'nouveau_document',
        message: 'Un nouveau document : « Attestation ».',
      }),
    ).toBe(false);
  });

  it('includes unread bulletin alerts in document alert filter', () => {
    const notif: Pick<Notification, 'type' | 'is_read' | 'message'> = {
      type: 'nouveau_bulletin',
      is_read: false,
      message: 'Votre bulletin de paie est disponible.',
    };
    expect(isUnreadDocumentAlertNotification(notif)).toBe(true);
  });

  it('resolves collaborateur_rh in employee view as employee context', () => {
    expect(resolveNotificationNavContext('collaborateur_rh', 'collaborateur')).toBe('employee');
  });
});

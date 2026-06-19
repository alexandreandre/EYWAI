import type { LucideIcon } from 'lucide-react';
import {
  AlertCircle,
  Bell,
  CheckCircle,
  Clock,
  Euro,
  FileCheck,
  FileText,
  Stethoscope,
  XCircle,
} from 'lucide-react';

import type { Notification } from '@/api/notifications';

export type NotificationNavContext = 'employee' | 'manager' | 'rh';

export function resolveNotificationNavContext(
  role: string | undefined,
  collaborateurRhViewMode?: string,
): NotificationNavContext {
  if (role === 'collaborateur') return 'employee';
  if (role === 'collaborateur_rh' && collaborateurRhViewMode === 'collaborateur') {
    return 'employee';
  }
  if (role === 'manager') return 'manager';
  return 'rh';
}

export const DOCUMENT_ALERT_NOTIFICATION_TYPES = [
  'nouveau_document',
  'nouveau_bulletin',
  'bulletin_participation_a_repondre',
  'bulletin_participation_rappel',
] as const;

export type DocumentAlertNotificationType =
  typeof DOCUMENT_ALERT_NOTIFICATION_TYPES[number];

export function isPayslipAlertNotification(
  notification: Pick<Notification, 'type' | 'message'>,
): boolean {
  return (
    notification.type === 'nouveau_bulletin' ||
    (notification.type === 'nouveau_document' &&
      notification.message.includes('Bulletin de paie'))
  );
}

export function isUnreadDocumentAlertNotification(
  notification: Pick<Notification, 'type' | 'is_read' | 'message'>,
): boolean {
  return (
    (DOCUMENT_ALERT_NOTIFICATION_TYPES.includes(
      notification.type as DocumentAlertNotificationType,
    ) ||
      isPayslipAlertNotification(notification)) &&
    !notification.is_read
  );
}

const TYPE_LABELS: Record<string, string> = {
  avenant_signe: 'Document signé',
  nouveau_document: 'Nouveau document',
  nouveau_bulletin: 'Nouveau bulletin',
  bulletin_participation_a_repondre: 'Bulletin participation',
  bulletin_participation_rappel: 'Rappel participation',
  bulletin_participation_retard_rh: 'Participation — retard',
  bulletin_participation_defaut_pee: 'Participation — défaut PEE',
  rappel_medical: 'Suivi médical',
  absence_soumise: 'Absence',
  absence_approuvee: 'Absence validée',
  absence_refusee: 'Absence refusée',
  absence_a_valider: 'À valider',
};

export function getNotificationTypeLabel(type: string): string {
  return TYPE_LABELS[type] ?? 'Notification';
}

export function getNotificationIcon(type: string): LucideIcon {
  switch (type) {
    case 'avenant_signe':
      return FileCheck;
    case 'nouveau_document':
      return FileText;
    case 'nouveau_bulletin':
    case 'bulletin_participation_a_repondre':
    case 'bulletin_participation_rappel':
      return Euro;
    case 'rappel_medical':
      return Stethoscope;
    case 'absence_soumise':
      return Clock;
    case 'absence_approuvee':
      return CheckCircle;
    case 'absence_refusee':
      return XCircle;
    case 'absence_a_valider':
      return AlertCircle;
    default:
      return Bell;
  }
}

export function getNotificationIconClass(type: string): string {
  switch (type) {
    case 'avenant_signe':
    case 'nouveau_document':
    case 'nouveau_bulletin':
    case 'absence_approuvee':
      return 'text-emerald-600';
    case 'rappel_medical':
    case 'absence_a_valider':
      return 'text-orange-600';
    case 'absence_soumise':
      return 'text-blue-600';
    case 'absence_refusee':
      return 'text-red-600';
    default:
      return 'text-muted-foreground';
  }
}

export function getNotificationHref(
  type: string,
  ctx: NotificationNavContext,
  message?: string,
): string | null {
  if (
    type === 'nouveau_bulletin' ||
    (type === 'nouveau_document' && message?.includes('Bulletin de paie'))
  ) {
    return ctx === 'employee' ? '/payslips' : '/payroll';
  }

  switch (type) {
    case 'avenant_signe':
    case 'nouveau_document':
      return ctx === 'employee' ? '/employee/documents' : '/documents';
    case 'nouveau_bulletin':
      return ctx === 'employee' ? '/payslips' : '/payroll';
    case 'rappel_medical':
      return ctx === 'employee' ? '/medical-follow-up' : '/medical-follow-up';
    case 'absence_soumise':
    case 'absence_approuvee':
    case 'absence_refusee':
      return ctx === 'employee' ? '/absences' : null;
    case 'absence_a_valider':
      if (ctx === 'manager') return '/leave-requests';
      if (ctx === 'rh') return '/leaves';
      return null;
    case 'cet_a_valider':
      if (ctx === 'manager') return '/cet-requests';
      if (ctx === 'rh') return '/suivi-cet';
      return null;
    case 'cet_demande_soumise':
    case 'cet_approuve':
    case 'cet_refuse':
    case 'cet_approuve_manager':
    case 'cet_refuse_manager':
      return ctx === 'employee' ? '/mon-cet' : '/suivi-cet';
    case 'bulletin_participation_a_repondre':
    case 'bulletin_participation_rappel':
      return ctx === 'employee' ? '/employee/participation' : '/saisies';
    case 'bulletin_participation_retard_rh':
    case 'bulletin_participation_defaut_pee':
      return ctx === 'rh' ? '/saisies' : null;
    default:
      return null;
  }
}

export function sortNotifications(items: Notification[]): Notification[] {
  return [...items].sort((a, b) => {
    if (a.is_read !== b.is_read) return a.is_read ? 1 : -1;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });
}

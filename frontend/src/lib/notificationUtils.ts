import type { LucideIcon } from 'lucide-react';
import {
  AlertCircle,
  Bell,
  CheckCircle,
  Clock,
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

const TYPE_LABELS: Record<string, string> = {
  avenant_signe: 'Document signé',
  nouveau_document: 'Nouveau document',
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
): string | null {
  switch (type) {
    case 'avenant_signe':
    case 'nouveau_document':
      return ctx === 'employee' ? '/employee/documents' : '/documents';
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

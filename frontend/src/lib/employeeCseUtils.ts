import type { MeetingListItem, MeetingStatus } from '@/api/cse';

export const EMPLOYEE_CSE_TABS = ['meetings', 'delegation', 'documents'] as const;
export type EmployeeCseTab = (typeof EMPLOYEE_CSE_TABS)[number];

export function isEmployeeCseTab(value: string | null): value is EmployeeCseTab {
  return value != null && (EMPLOYEE_CSE_TABS as readonly string[]).includes(value);
}

const MEETING_STATUS_ORDER: Record<MeetingStatus, number> = {
  a_venir: 0,
  en_cours: 1,
  terminee: 2,
};

export function sortMeetingsByUrgency(meetings: MeetingListItem[]): MeetingListItem[] {
  return [...meetings].sort((a, b) => {
    const statusDiff = MEETING_STATUS_ORDER[a.status] - MEETING_STATUS_ORDER[b.status];
    if (statusDiff !== 0) return statusDiff;
    const dateA = new Date(a.meeting_date).getTime();
    const dateB = new Date(b.meeting_date).getTime();
    if (a.status === 'a_venir') return dateA - dateB;
    return dateB - dateA;
  });
}

export function pickNextMeeting(meetings: MeetingListItem[]): MeetingListItem | null {
  const upcoming = meetings
    .filter((m) => m.status === 'a_venir' || m.status === 'en_cours')
    .sort(
      (a, b) =>
        new Date(a.meeting_date).getTime() - new Date(b.meeting_date).getTime()
    );
  return upcoming[0] ?? null;
}

export function formatCseDate(dateString: string): string {
  try {
    return new Date(dateString).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  } catch {
    return dateString;
  }
}

export function formatCseTime(timeString: string | null | undefined): string {
  if (!timeString) return '';
  try {
    return timeString.substring(0, 5);
  } catch {
    return timeString;
  }
}

export function formatMonthYearLabel(date: Date): string {
  const label = date.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export function formatPublishedAt(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

export function mandateDaysRemaining(endDate: string): number | null {
  try {
    return Math.ceil(
      (new Date(endDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
    );
  } catch {
    return null;
  }
}

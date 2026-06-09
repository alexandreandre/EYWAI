import apiClient from '@/api/apiClient';

export type HrDeadlineReminderType = 'cdd_end' | 'trial_end' | 'residence_permit';

export type HrDeadlineCandidate = {
  employee_id: string;
  first_name: string;
  last_name: string;
  reminder_type: HrDeadlineReminderType;
  deadline: string;
  days_remaining: number;
  label: string;
};

export async function fetchHrDeadlineCandidates(): Promise<HrDeadlineCandidate[]> {
  const { data } = await apiClient.get<HrDeadlineCandidate[]>(
    '/api/hr-deadline-reminders/candidates',
  );
  return data ?? [];
}

import apiClient from '@/api/apiClient';

export type SlotDetection = 'shift_code' | 'nearest_entry' | 'planning_first';
export type PunchReviewStatus = 'pending' | 'approved' | 'rejected';

export interface PunchAccountingSettings {
  configured: boolean;
  enabled: boolean;
  tolerance_minutes: number;
  default_break_deduct_minutes: number;
  use_last_nonzero_exit: boolean;
  slot_detection: SlotDetection;
  within_tolerance_pay_theoretical: boolean;
  require_manager_validation_for_overtime: boolean;
}

export type PunchAccountingSettingsUpdate = Partial<
  Omit<PunchAccountingSettings, 'configured'>
>;

export interface PunchShiftSlot {
  id: string;
  code?: string | null;
  label: string;
  entry_time: string;
  exit_time: string;
  theoretical_gross_minutes: number;
  break_deduct_minutes: number;
  paid_lunch_break: boolean;
  sort_order: number;
}

export interface PunchShiftSlotCreate {
  code?: string | null;
  label?: string;
  entry_time: string;
  exit_time: string;
  theoretical_gross_minutes?: number;
  break_deduct_minutes?: number;
  paid_lunch_break?: boolean;
  sort_order?: number;
}

export interface PunchOvertimeReview {
  id: string;
  employee_id: string;
  employee_name?: string | null;
  work_date: string;
  overtime_hours: number;
  reason: string;
  raw_entry_time?: string | null;
  raw_exit_time?: string | null;
  status: PunchReviewStatus;
  review_note?: string | null;
}

export const getPunchAccountingSettings = async (): Promise<PunchAccountingSettings> => {
  const { data } = await apiClient.get<PunchAccountingSettings>(
    '/api/schedules/punch-accounting/settings',
  );
  return data;
};

export const updatePunchAccountingSettings = async (
  payload: PunchAccountingSettingsUpdate,
): Promise<PunchAccountingSettings> => {
  const { data } = await apiClient.patch<PunchAccountingSettings>(
    '/api/schedules/punch-accounting/settings',
    payload,
  );
  return data;
};

export const applyPunchAccountingPreset = async (
  preset: string,
): Promise<{ settings: PunchAccountingSettings; slots: PunchShiftSlot[] }> => {
  const { data } = await apiClient.post<{ settings: PunchAccountingSettings; slots: PunchShiftSlot[] }>(
    `/api/schedules/punch-accounting/settings/apply-preset/${preset}`,
  );
  return data;
};

export const listPunchShiftSlots = async (): Promise<PunchShiftSlot[]> => {
  const { data } = await apiClient.get<PunchShiftSlot[]>('/api/schedules/punch-accounting/slots');
  return data;
};

export const createPunchShiftSlot = async (
  payload: PunchShiftSlotCreate,
): Promise<PunchShiftSlot> => {
  const { data } = await apiClient.post<PunchShiftSlot>(
    '/api/schedules/punch-accounting/slots',
    payload,
  );
  return data;
};

export const deletePunchShiftSlot = async (slotId: string): Promise<void> => {
  await apiClient.delete(`/api/schedules/punch-accounting/slots/${slotId}`);
};

export const listPunchOvertimeReviews = async (
  year: number,
  month: number,
  status?: PunchReviewStatus,
): Promise<PunchOvertimeReview[]> => {
  const { data } = await apiClient.get<PunchOvertimeReview[]>(
    '/api/schedules/punch-overtime-reviews',
    { params: { year, month, status } },
  );
  return data;
};

export const updatePunchOvertimeReview = async (
  reviewId: string,
  payload: { status: PunchReviewStatus; review_note?: string },
): Promise<PunchOvertimeReview> => {
  const { data } = await apiClient.patch<PunchOvertimeReview>(
    `/api/schedules/punch-overtime-reviews/${reviewId}`,
    payload,
  );
  return data;
};

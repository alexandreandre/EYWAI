import apiClient from '@/api/apiClient';
import type { Shift } from '@/api/planning';

export interface EmployeeWeekPlanning {
  week_start: string;
  week_end: string;
  status: string;
  team_view_enabled: boolean;
  /** Fiche employees.id résolue côté serveur (vision équipe, etc.). */
  employee_id?: string;
  shifts: Shift[];
}

import { downloadBlob as triggerDownload } from '@/lib/downloadBlob';


/** Retire les champs non destinés à l’affichage collaborateur (défense en profondeur). */
function sanitizeShifts(shifts: Shift[]): Shift[] {
  return shifts.map((s) => {
    const { comment_internal: _omit, ...rest } = s;
    return rest as Shift;
  });
}

export async function getMyPlanning(weekStart: string): Promise<EmployeeWeekPlanning> {
  const { data } = await apiClient.get<EmployeeWeekPlanning>('/api/planning/me', {
    params: { week_start: weekStart },
  });
  return {
    ...data,
    shifts: sanitizeShifts(data.shifts ?? []),
  };
}

export async function exportPlanningPDF(weekStart: string): Promise<Blob> {
  const { data } = await apiClient.get<Blob>('/api/planning/me/export/pdf', {
    params: { week_start: weekStart },
    responseType: 'blob',
  });
  const safe = weekStart.slice(0, 10);
  const name = `planning-${safe}.pdf`;
  triggerDownload(data, name);
  return data;
}

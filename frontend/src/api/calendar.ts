// src/api/calendar.ts

import apiClient from './apiClient';

// --- INTERFACES POUR LE CALENDRIER ---
// Ces types décrivent la forme des données échangées avec l'API.
// Ils correspondent exactement aux modèles Pydantic du backend.

export interface PlannedEventData {
  jour: number;
  type: string;
  heures_prevues: number | null;
}

export interface ActualHoursData {
  jour: number;
  type: string | null;
  heures_faites: number | null;
}

// --- FONCTIONS D'API ---

/**
 * Récupère le calendrier prévu pour un employé.
 */
export const getPlannedCalendar = (employeeId: string, year: number, month: number) => {
  return apiClient.get(`/api/employees/${employeeId}/planned-calendar`, {
    params: { year, month }
  });
};

/**
 * Met à jour le calendrier prévu pour un employé.
 */
export const updatePlannedCalendar = (employeeId: string, year: number, month: number, data: PlannedEventData[]) => {
  return apiClient.post(`/api/employees/${employeeId}/planned-calendar`, {
    year,
    month,
    calendrier_prevu: data,
  });
};

/**
 * Récupère les heures réelles saisies pour un employé.
 */
export const getActualHours = (employeeId: string, year: number, month: number) => {
  return apiClient.get(`/api/employees/${employeeId}/actual-hours`, {
    params: { year, month }
  });
};

/**
 * Met à jour les heures réelles saisies pour un employé.
 */
export const updateActualHours = (employeeId: string, year: number, month: number, data: ActualHoursData[]) => {
  return apiClient.post(`/api/employees/${employeeId}/actual-hours`, {
    year,
    month,
    calendrier_reel: data,
  });
};

export const calculatePayrollEvents = (employeeId: string, year: number, month: number) => {
  return apiClient.post(`/api/employees/${employeeId}/calculate-payroll-events`, {
    year,
    month,
  });
};

// --- SAISIE ASSISTÉE PAR IA (page Calendriers RH) ---

export interface RosterEmployee {
  id: string;
  first_name: string;
  last_name: string;
}

export type DayNature = 'prevu' | 'reel';

export interface AiDayEntry {
  jour: number;
  heures: number | null;
  type: string;
  nature: DayNature;
}

export type AiMatchConfidence = 'high' | 'medium' | 'none';

export interface AiEmployeeProposal {
  raw_name: string;
  employee_id: string | null;
  matched_name: string | null;
  match_confidence: AiMatchConfidence;
  days: AiDayEntry[];
  warnings: string[];
}

export interface AiCalendarProposal {
  year: number;
  month: number;
  source: string;
  employees: AiEmployeeProposal[];
  warnings: string[];
}

/**
 * Analyse une instruction en langage naturel (texte ou dictée transcrite)
 * et renvoie une proposition d'heures réelles (non persistée).
 */
export const parseScheduleInstruction = async (
  year: number,
  month: number,
  instruction: string,
  employees: RosterEmployee[],
  singleEmployee = false,
): Promise<AiCalendarProposal> => {
  const { data } = await apiClient.post<AiCalendarProposal>(
    '/api/schedules/assisted-fill/parse-text',
    { year, month, instruction, employees, single_employee: singleEmployee },
  );
  return data;
};

/**
 * Analyse un relevé de pointeuse (PDF / image) et renvoie une proposition
 * d'heures réelles (non persistée).
 */
export const extractTimesheet = async (
  file: File,
  year: number,
  month: number,
  employees: RosterEmployee[],
  singleEmployee = false,
): Promise<AiCalendarProposal> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('year', String(year));
  formData.append('month', String(month));
  formData.append('employees', JSON.stringify(employees));
  formData.append('single_employee', String(singleEmployee));
  const { data } = await apiClient.post<AiCalendarProposal>(
    '/api/schedules/assisted-fill/extract-timesheet',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
};
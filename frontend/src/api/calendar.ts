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
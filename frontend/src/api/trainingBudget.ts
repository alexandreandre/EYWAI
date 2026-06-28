import axios from 'axios';
import apiClient from "./apiClient";

export type TrainingBudgetAlertLevel = "none" | "warning" | "critical";

export type TrainingBudget = {
  id: string;
  company_id: string;
  year: number;
  global_envelope: number;
  alert_threshold_1: number;
  alert_threshold_2: number;
  service_breakdown: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type TrainingBudgetWithConsumption = TrainingBudget & {
  consumed: number;
  remaining: number;
  consumption_pct: number;
  alert_level: TrainingBudgetAlertLevel;
};

export type TrainingBudgetSave = {
  global_envelope: number;
  alert_threshold_1?: number;
  alert_threshold_2?: number;
  service_breakdown?: Record<string, unknown>;
};

export async function getBudget(year: number): Promise<TrainingBudgetWithConsumption | null> {
  try {
    const res = await apiClient.get<TrainingBudgetWithConsumption>(`/api/training-budget/${year}`);
    return res.data;
  } catch (e) {
    if (axios.isAxiosError(e) && e.response?.status === 404) {
      return null;
    }
    throw e;
  }
}

export async function getAllBudgets(): Promise<TrainingBudgetWithConsumption[]> {
  const res = await apiClient.get<TrainingBudgetWithConsumption[]>("/api/training-budget");
  return res.data ?? [];
}

export async function saveBudget(
  year: number,
  data: TrainingBudgetSave,
): Promise<TrainingBudgetWithConsumption> {
  const res = await apiClient.put<TrainingBudgetWithConsumption>(`/api/training-budget/${year}`, {
    global_envelope: data.global_envelope,
    alert_threshold_1: data.alert_threshold_1 ?? 70,
    alert_threshold_2: data.alert_threshold_2 ?? 90,
    service_breakdown: data.service_breakdown ?? {},
  });
  return res.data;
}

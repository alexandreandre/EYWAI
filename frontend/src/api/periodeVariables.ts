import apiClient from '@/api/apiClient';

/** Fenêtre sur laquelle les heures sup et les paniers d'un mois sont comptés. */
export interface PeriodeVariables {
  debut: string;
  fin: string;
  origine: 'regle' | 'manuel';
  semaines: number[];
  mois_civil: [string, string];
  report_debut: string;
}

/** Un mois dont la fenêtre a été corrigée à la main. */
export interface PeriodeVariablesSurcharge {
  month: number;
  debut: string;
  fin: string;
}

export async function getPeriodeVariables(
  year: number,
  month: number,
): Promise<PeriodeVariables> {
  const { data } = await apiClient.get<PeriodeVariables>('/api/payroll-variables/period', {
    params: { year, month },
  });
  return data;
}

export async function putPeriodeVariables(
  year: number,
  month: number,
  fin: string,
): Promise<PeriodeVariables> {
  const { data } = await apiClient.put<PeriodeVariables>('/api/payroll-variables/period', {
    year,
    month,
    fin,
  });
  return data;
}

export async function getSurchargesPeriodeVariables(
  year: number,
): Promise<PeriodeVariablesSurcharge[]> {
  const { data } = await apiClient.get<PeriodeVariablesSurcharge[]>(
    '/api/payroll-variables/periods',
    { params: { year } },
  );
  return data;
}

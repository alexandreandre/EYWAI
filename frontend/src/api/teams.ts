import apiClient from '@/api/apiClient';

export interface Team {
  id: string;
  company_id: string;
  name: string;
  description?: string;
  color: string;
  manager_employee_id?: string;
  manager_first_name?: string;
  manager_last_name?: string;
  status: 'active' | 'archived';
  employee_count: number;
  created_at: string;
  updated_at: string;
}

export interface TeamListResponse {
  teams: Team[];
  total: number;
  archived_count: number;
}

export interface TeamAnalyticsItem {
  team_id?: string;
  team_name: string;
  team_color: string;
  employee_count: number;
  masse_salariale_brute: number;
  masse_salariale_totale: number;
  notes_de_frais: number;
  absences_jours: number;
  taux_absenteisme: number;
  cout_moyen_par_salarie: number;
}

export interface TeamAnalyticsResponse {
  period_start: string;
  period_end: string;
  items: TeamAnalyticsItem[];
  total_employees: number;
  total_masse_brute: number;
  total_notes_de_frais: number;
}

export const TEAM_COLORS = [
  '#6366f1',
  '#8b5cf6',
  '#ec4899',
  '#ef4444',
  '#f97316',
  '#eab308',
  '#22c55e',
  '#14b8a6',
  '#06b6d4',
  '#3b82f6',
  '#64748b',
  '#78716c',
];

export type TeamCreatePayload = {
  name: string;
  description?: string;
  color?: string;
  manager_employee_id?: string;
};

export type TeamUpdateBody = Partial<{
  name: string;
  description: string | null;
  color: string;
  manager_employee_id: string | null;
}>;

export async function getTeams(
  includeArchived?: boolean,
): Promise<TeamListResponse> {
  const { data } = await apiClient.get<TeamListResponse>('/api/teams', {
    params: { include_archived: includeArchived ?? false },
  });
  return data;
}

export async function createTeam(payload: TeamCreatePayload): Promise<Team> {
  const { data } = await apiClient.post<Team>('/api/teams', payload);
  return data;
}

export async function updateTeam(
  teamId: string,
  body: TeamUpdateBody,
): Promise<Team> {
  const payload = Object.fromEntries(
    Object.entries(body).filter(([, v]) => v !== undefined),
  );
  const { data } = await apiClient.patch<Team>(
    `/api/teams/${teamId}`,
    payload,
  );
  return data;
}

export async function archiveTeam(teamId: string): Promise<Team> {
  const { data } = await apiClient.post<Team>(
    `/api/teams/${teamId}/archive`,
  );
  return data;
}

export async function reactivateTeam(teamId: string): Promise<Team> {
  const { data } = await apiClient.post<Team>(
    `/api/teams/${teamId}/reactivate`,
  );
  return data;
}

export async function deleteTeam(teamId: string): Promise<void> {
  await apiClient.delete(`/api/teams/${teamId}`);
}

export async function assignEmployeeTeam(
  employeeId: string,
  teamId: string | null,
): Promise<void> {
  await apiClient.patch(`/api/teams/employees/${employeeId}/team`, {
    team_id: teamId,
  });
}

export async function checkTeamName(
  name: string,
  excludeTeamId?: string,
): Promise<{ available: boolean; name: string }> {
  const { data } = await apiClient.get<{ available: boolean; name: string }>(
    '/api/teams/check-name',
    {
      params: {
        name,
        ...(excludeTeamId ? { exclude_team_id: excludeTeamId } : {}),
      },
    },
  );
  return data;
}

export async function getTeamAnalytics(params: {
  period_start: string;
  period_end: string;
  team_ids?: string[];
}): Promise<TeamAnalyticsResponse> {
  const sp = new URLSearchParams();
  sp.set('period_start', params.period_start);
  sp.set('period_end', params.period_end);
  for (const id of params.team_ids ?? []) {
    if (id) sp.append('team_ids', id);
  }
  const { data } = await apiClient.get<TeamAnalyticsResponse>(
    `/api/teams/analytics?${sp.toString()}`,
  );
  return data;
}

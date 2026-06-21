import type { WeekTemplate } from '@/hooks/useCalendar';
import {
  createWeekTemplate,
  deleteWeekTemplate as deleteWeekTemplateApi,
  listWeekTemplates,
  type WeekScheduleTemplate,
} from '@/api/modulation';

export interface SavedWeekTemplate {
  id?: string;
  name: string;
  template: WeekTemplate;
  modulation_tier?: 'high' | 'low' | 'neutral';
  team_id?: string | null;
}

const MAX_TEMPLATES = 50;

function weekTemplateToDayConfigs(template: WeekTemplate): Record<string, unknown>[] {
  return [1, 2, 3, 4, 5].map((day) => {
    const raw = template[day];
    const hours = raw === '1' ? 1 : parseFloat(String(raw || '0')) || 0;
    return {
      day,
      hours,
      type: hours > 0 ? 'travail' : 'repos',
    };
  });
}

function dayConfigsToWeekTemplate(
  configs: Record<string, unknown>[] | undefined,
): WeekTemplate {
  const tpl: WeekTemplate = {};
  for (const cfg of configs || []) {
    const day = Number(cfg.day);
    if (day >= 1 && day <= 5) {
      const hours = cfg.hours;
      if (hours === 1 && cfg.type === 'travail') {
        tpl[day] = '1';
      } else {
        tpl[day] = String(hours ?? '0');
      }
    }
  }
  return tpl;
}

function templateFromApi(row: WeekScheduleTemplate): SavedWeekTemplate {
  return {
    id: row.id,
    name: row.name,
    template: dayConfigsToWeekTemplate(row.day_configs),
    modulation_tier: row.modulation_tier,
    team_id: row.team_id,
  };
}

/** Charge les modèles depuis l'API (source unique). */
export async function loadSavedWeekTemplates(
  companyId: string,
  employeeTeamId?: string | null,
): Promise<SavedWeekTemplate[]> {
  if (!companyId) return [];
  const rows = await listWeekTemplates();
  const mapped = rows.map(templateFromApi).slice(0, MAX_TEMPLATES);
  if (!employeeTeamId) return mapped;
  return mapped.filter((t) => !t.team_id || t.team_id === employeeTeamId);
}

/** Enregistre un modèle en base. */
export async function saveWeekTemplate(
  companyId: string,
  name: string,
  template: WeekTemplate,
  modulationTier: 'high' | 'low' | 'neutral' = 'neutral',
): Promise<SavedWeekTemplate[]> {
  const trimmed = name.trim().slice(0, 40);
  if (!trimmed || !companyId) return [];

  const weeklyHours = [1, 2, 3, 4, 5].reduce((sum, day) => {
    const raw = template[day];
    if (raw === '1') return sum + 1;
    return sum + (parseFloat(String(raw || '0')) || 0);
  }, 0);

  await createWeekTemplate({
    name: trimmed,
    weekly_hours: weeklyHours,
    day_configs: weekTemplateToDayConfigs(template),
    modulation_tier: modulationTier,
    is_active: true,
  });
  return loadSavedWeekTemplates(companyId);
}

export async function deleteWeekTemplate(
  companyId: string,
  templateIdOrName: string,
): Promise<SavedWeekTemplate[]> {
  const rows = await listWeekTemplates();
  const match = rows.find(
    (r) => r.id === templateIdOrName || r.name === templateIdOrName,
  );
  if (match?.id) {
    await deleteWeekTemplateApi(match.id);
  }
  return loadSavedWeekTemplates(companyId);
}

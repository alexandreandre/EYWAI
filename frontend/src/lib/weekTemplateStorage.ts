import type { WeekTemplate } from '@/hooks/useCalendar';
import {
  createWeekTemplate,
  listWeekTemplates,
  type WeekScheduleTemplate,
} from '@/api/modulation';

export interface SavedWeekTemplate {
  id?: string;
  name: string;
  template: WeekTemplate;
  modulation_tier?: 'high' | 'low' | 'neutral';
}

const MAX_TEMPLATES = 10;

function storageKey(companyId: string): string {
  return `eywai-week-templates-${companyId || 'default'}`;
}

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
  };
}

function loadLocalTemplates(companyId: string): SavedWeekTemplate[] {
  try {
    const raw = localStorage.getItem(storageKey(companyId));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SavedWeekTemplate[];
    return Array.isArray(parsed) ? parsed.slice(0, MAX_TEMPLATES) : [];
  } catch {
    return [];
  }
}

function saveLocalTemplates(companyId: string, templates: SavedWeekTemplate[]): void {
  localStorage.setItem(storageKey(companyId), JSON.stringify(templates.slice(0, MAX_TEMPLATES)));
}

/** Charge les modèles depuis l'API (fallback localStorage si indisponible). */
export async function loadSavedWeekTemplates(
  companyId: string,
): Promise<SavedWeekTemplate[]> {
  if (!companyId) return [];
  try {
    const rows = await listWeekTemplates();
    if (rows.length > 0) {
      return rows.map(templateFromApi).slice(0, MAX_TEMPLATES);
    }
  } catch {
    // API indisponible — fallback local
  }
  return loadLocalTemplates(companyId);
}

/** Enregistre un modèle en base (fallback localStorage). */
export async function saveWeekTemplate(
  companyId: string,
  name: string,
  template: WeekTemplate,
  modulationTier: 'high' | 'low' | 'neutral' = 'neutral',
): Promise<SavedWeekTemplate[]> {
  const trimmed = name.trim().slice(0, 40);
  if (!trimmed || !companyId) return loadLocalTemplates(companyId);

  const weeklyHours = [1, 2, 3, 4, 5].reduce((sum, day) => {
    const raw = template[day];
    if (raw === '1') return sum + 1;
    return sum + (parseFloat(String(raw || '0')) || 0);
  }, 0);

  try {
    await createWeekTemplate({
      name: trimmed,
      weekly_hours: weeklyHours,
      day_configs: weekTemplateToDayConfigs(template),
      modulation_tier: modulationTier,
      is_active: true,
    });
    return loadSavedWeekTemplates(companyId);
  } catch {
    const existing = loadLocalTemplates(companyId).filter((t) => t.name !== trimmed);
    const next = [{ name: trimmed, template, modulation_tier: modulationTier }, ...existing].slice(
      0,
      MAX_TEMPLATES,
    );
    saveLocalTemplates(companyId, next);
    return next;
  }
}

export async function deleteWeekTemplate(
  companyId: string,
  name: string,
): Promise<SavedWeekTemplate[]> {
  const local = loadLocalTemplates(companyId).filter((t) => t.name !== name);
  saveLocalTemplates(companyId, local);
  return loadSavedWeekTemplates(companyId);
}

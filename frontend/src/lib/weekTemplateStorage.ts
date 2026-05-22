import type { WeekTemplate } from '@/hooks/useCalendar';

export interface SavedWeekTemplate {
  name: string;
  template: WeekTemplate;
}

const MAX_TEMPLATES = 3;

function storageKey(companyId: string): string {
  return `eywai-week-templates-${companyId || 'default'}`;
}

export function loadSavedWeekTemplates(companyId: string): SavedWeekTemplate[] {
  try {
    const raw = localStorage.getItem(storageKey(companyId));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SavedWeekTemplate[];
    return Array.isArray(parsed) ? parsed.slice(0, MAX_TEMPLATES) : [];
  } catch {
    return [];
  }
}

export function saveWeekTemplate(
  companyId: string,
  name: string,
  template: WeekTemplate
): SavedWeekTemplate[] {
  const trimmed = name.trim().slice(0, 40);
  if (!trimmed) return loadSavedWeekTemplates(companyId);

  const existing = loadSavedWeekTemplates(companyId).filter((t) => t.name !== trimmed);
  const next = [{ name: trimmed, template }, ...existing].slice(0, MAX_TEMPLATES);
  localStorage.setItem(storageKey(companyId), JSON.stringify(next));
  return next;
}

export function deleteWeekTemplate(companyId: string, name: string): SavedWeekTemplate[] {
  const next = loadSavedWeekTemplates(companyId).filter((t) => t.name !== name);
  localStorage.setItem(storageKey(companyId), JSON.stringify(next));
  return next;
}

/**
 * Utilitaires onboarding — dates J+x, retards, tri et liens profonds (front uniquement).
 */

import type { OnboardingTask } from "@/api/onboarding";

export const ONBOARDING_LOOKBACK_DAYS = 90;
export const ONBOARDING_RECENT_HIRE_MONTHS = 6;

export type OnboardingEmployeeHeader = {
  first_name: string;
  last_name: string;
  job_title?: string | null;
  hire_date?: string | null;
  contract_type?: string | null;
  statut?: string | null;
  periode_essai?: Record<string, unknown> | null;
};

export type TaskFilter = "all" | "todo" | "overdue" | "done";

export type TaskUrgency = "overdue" | "soon" | "todo" | "done";

export type OnboardingTaskStats = {
  todo: number;
  overdue: number;
  done: number;
};

const MS_PER_DAY = 86_400_000;

export function parseDateOnly(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const d = iso.includes("T") ? new Date(iso) : new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

export function formatDateFR(
  iso: string | null | undefined,
  style: "short" | "long" = "short",
): string {
  const d = parseDateOnly(iso);
  if (!d) return "";
  return d.toLocaleDateString("fr-FR", { dateStyle: style });
}

export function daysSinceHire(hireDate: string | null | undefined, ref = new Date()): number | null {
  const hire = parseDateOnly(hireDate);
  if (!hire) return null;
  const diff = startOfDay(ref).getTime() - startOfDay(hire).getTime();
  return Math.max(0, Math.floor(diff / MS_PER_DAY));
}

export function computeDueDate(
  hireDate: string | null | undefined,
  dueDays: number | null | undefined,
): Date | null {
  const hire = parseDateOnly(hireDate);
  if (!hire || dueDays == null) return null;
  const due = new Date(hire);
  due.setDate(due.getDate() + dueDays);
  return due;
}

export function getTaskUrgency(
  task: OnboardingTask,
  hireDate: string | null | undefined,
  ref = new Date(),
): TaskUrgency {
  if (task.is_completed) return "done";
  const due = computeDueDate(hireDate, task.due_days);
  if (!due) return "todo";
  const today = startOfDay(ref).getTime();
  const dueTs = startOfDay(due).getTime();
  if (dueTs < today) return "overdue";
  const daysUntil = Math.floor((dueTs - today) / MS_PER_DAY);
  if (daysUntil <= 7) return "soon";
  return "todo";
}

export function isTaskOverdue(
  task: OnboardingTask,
  hireDate: string | null | undefined,
  ref = new Date(),
): boolean {
  return getTaskUrgency(task, hireDate, ref) === "overdue";
}

const URGENCY_ORDER: Record<TaskUrgency, number> = {
  overdue: 0,
  soon: 1,
  todo: 2,
  done: 3,
};

export function sortTasksByUrgency(
  tasks: OnboardingTask[],
  hireDate: string | null | undefined,
): OnboardingTask[] {
  return [...tasks].sort((a, b) => {
    const ua = getTaskUrgency(a, hireDate);
    const ub = getTaskUrgency(b, hireDate);
    if (URGENCY_ORDER[ua] !== URGENCY_ORDER[ub]) {
      return URGENCY_ORDER[ua] - URGENCY_ORDER[ub];
    }
    return a.position - b.position;
  });
}

export function countTaskStats(
  tasks: OnboardingTask[],
  hireDate: string | null | undefined,
  ref = new Date(),
): OnboardingTaskStats {
  let todo = 0;
  let overdue = 0;
  let done = 0;
  for (const t of tasks) {
    if (t.is_completed) {
      done += 1;
      continue;
    }
    if (isTaskOverdue(t, hireDate, ref)) overdue += 1;
    else todo += 1;
  }
  return { todo, overdue, done };
}

export function filterTasks(
  tasks: OnboardingTask[],
  filter: TaskFilter,
  hireDate: string | null | undefined,
  ref = new Date(),
): OnboardingTask[] {
  if (filter === "all") return tasks;
  return tasks.filter((t) => {
    if (filter === "done") return t.is_completed;
    if (filter === "todo") return !t.is_completed;
    if (filter === "overdue") return isTaskOverdue(t, hireDate, ref);
    return true;
  });
}

export function isRecentHire(
  hireDate: string | null | undefined,
  months = ONBOARDING_RECENT_HIRE_MONTHS,
): boolean {
  const hire = parseDateOnly(hireDate);
  if (!hire) return false;
  const cutoff = new Date();
  cutoff.setMonth(cutoff.getMonth() - months);
  return hire >= startOfDay(cutoff);
}

export function isWithinLookback(hireDate: string | null | undefined, days = ONBOARDING_LOOKBACK_DAYS): boolean {
  const hire = parseDateOnly(hireDate);
  if (!hire) return false;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - days);
  return hire >= startOfDay(cutoff);
}

export function formatPeriodeEssaiEnd(
  hireDate: string | null | undefined,
  periodeEssai: Record<string, unknown> | null | undefined,
): string | null {
  const hire = parseDateOnly(hireDate);
  if (!hire || !periodeEssai) return null;
  const duree = Number(periodeEssai.duree_initiale ?? periodeEssai.duree);
  const unite = String(periodeEssai.unite ?? "mois").toLowerCase();
  if (!duree || Number.isNaN(duree)) return null;
  const end = new Date(hire);
  if (unite.startsWith("jour")) end.setDate(end.getDate() + duree);
  else if (unite.startsWith("sem")) end.setDate(end.getDate() + duree * 7);
  else end.setMonth(end.getMonth() + duree);
  return end.toLocaleDateString("fr-FR", { dateStyle: "long" });
}

export function formatEmployeeMetaLine(employee: OnboardingEmployeeHeader): string {
  const parts: string[] = [];
  if (employee.contract_type) parts.push(employee.contract_type);
  if (employee.statut) parts.push(employee.statut);
  const hireLabel = formatDateFR(employee.hire_date, "long");
  if (hireLabel) parts.push(`Embauché le ${hireLabel}`);
  const j = daysSinceHire(employee.hire_date);
  if (j != null) parts.push(`J+${j}`);
  const peEnd = formatPeriodeEssaiEnd(employee.hire_date, employee.periode_essai);
  if (peEnd) parts.push(`Fin période d'essai ${peEnd}`);
  return parts.join(" · ");
}

export type TaskDeepLink = { label: string; href: string };

/** Liens profonds optionnels par titre de tâche (mappage front). */
export function getTaskDeepLink(
  task: OnboardingTask,
  employeeId: string,
): TaskDeepLink | null {
  const title = task.title.toLowerCase();
  if (
    title.includes("document") ||
    title.includes("contrat") ||
    title.includes("collecter")
  ) {
    return {
      label: "Documents du salarié",
      href: `/employees/${employeeId}?tab=documents`,
    };
  }
  if (title.includes("formation") || title.includes("règlement")) {
    return {
      label: "Formation",
      href: `/employee/formation#onboarding`,
    };
  }
  if (title.includes("eywai") || title.includes("accès email") || title.includes("outils")) {
    return {
      label: "Gestion des utilisateurs",
      href: "/users",
    };
  }
  if (title.includes("badge") || title.includes("locaux")) {
    return { label: "Planning", href: "/schedules" };
  }
  return null;
}

export type TimelineMilestone = {
  day: number;
  label: string;
  status: "done" | "partial" | "pending" | "overdue";
  completed: number;
  total: number;
};

export function buildTimelineMilestones(
  tasks: OnboardingTask[],
  hireDate: string | null | undefined,
  ref = new Date(),
): TimelineMilestone[] {
  const milestones = [
    { day: 1, label: "J+1" },
    { day: 7, label: "J+7" },
    { day: 30, label: "J+30" },
  ];
  const j = daysSinceHire(hireDate, ref) ?? 0;

  return milestones.map(({ day, label }) => {
    const inWindow = tasks.filter(
      (t) => t.due_days != null && t.due_days <= day,
    );
    const total = inWindow.length;
    const completed = inWindow.filter((t) => t.is_completed).length;
    const hasOverdue = inWindow.some(
      (t) => !t.is_completed && isTaskOverdue(t, hireDate, ref),
    );

    let status: TimelineMilestone["status"] = "pending";
    if (total > 0 && completed === total) status = "done";
    else if (completed > 0) status = "partial";
    else if (j >= day && hasOverdue) status = "overdue";

    return { day, label, status, completed, total };
  });
}

export type HubStatus = "not_started" | "in_progress" | "completed";

export function getHubStatus(
  progressPct: number,
  completedAt: string | null | undefined,
): HubStatus {
  if (completedAt || progressPct >= 100) return "completed";
  if (progressPct <= 0) return "not_started";
  return "in_progress";
}

export const HUB_STATUS_LABELS: Record<HubStatus, string> = {
  not_started: "À démarrer",
  in_progress: "En cours",
  completed: "Terminé",
};

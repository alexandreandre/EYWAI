import { Link } from "react-router-dom";
import { ExternalLink } from "lucide-react";

import type { OnboardingTask } from "@/api/onboarding";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import {
  computeDueDate,
  getTaskDeepLink,
  getTaskUrgency,
  type OnboardingEmployeeHeader,
} from "@/lib/onboardingUtils";

type OnboardingTaskItemProps = {
  task: OnboardingTask;
  employeeId: string;
  hireDate: OnboardingEmployeeHeader["hire_date"];
  isRh: boolean;
  onToggle: (taskId: string, checked: boolean) => void;
  toggling: boolean;
};

const URGENCY_BADGE: Record<
  ReturnType<typeof getTaskUrgency>,
  { label: string; variant: "destructive" | "secondary" | "outline" } | null
> = {
  overdue: { label: "En retard", variant: "destructive" },
  soon: { label: "Cette semaine", variant: "secondary" },
  todo: null,
  done: null,
};

export function OnboardingTaskItem({
  task,
  employeeId,
  hireDate,
  isRh,
  onToggle,
  toggling,
}: OnboardingTaskItemProps) {
  const urgency = getTaskUrgency(task, hireDate);
  const urgencyBadge = URGENCY_BADGE[urgency];
  const dueDate = computeDueDate(hireDate, task.due_days);
  const deepLink = getTaskDeepLink(task, employeeId);

  return (
    <li className="flex gap-3 rounded-lg border bg-card p-3 text-sm items-start print:break-inside-avoid">
      {isRh ? (
        <Checkbox
          checked={task.is_completed}
          disabled={toggling}
          onCheckedChange={(v) => {
            if (v === true) onToggle(task.id, true);
            else if (v === false) onToggle(task.id, false);
          }}
          className="mt-0.5"
          aria-label={task.title}
        />
      ) : (
        <Checkbox
          checked={task.is_completed}
          disabled
          className="mt-0.5"
          aria-label={task.title}
        />
      )}
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={cn(
              "font-medium",
              task.is_completed && "line-through text-muted-foreground",
            )}
          >
            {task.title}
          </span>
          {task.due_days != null ? (
            <Badge variant="outline" className="text-[10px] h-5 tabular-nums">
              J+{task.due_days}
              {dueDate
                ? ` · ${dueDate.toLocaleDateString("fr-FR", { dateStyle: "short" })}`
                : ""}
            </Badge>
          ) : null}
          {urgencyBadge ? (
            <Badge variant={urgencyBadge.variant} className="text-[10px] h-5">
              {urgencyBadge.label}
            </Badge>
          ) : null}
        </div>
        {task.description ? (
          <p className="text-xs text-muted-foreground">{task.description}</p>
        ) : null}
        {task.is_completed && task.completed_at ? (
          <p className="text-[11px] text-muted-foreground">
            Complété le{" "}
            {new Date(task.completed_at).toLocaleString("fr-FR", {
              dateStyle: "short",
              timeStyle: "short",
            })}
          </p>
        ) : null}
        {deepLink && !task.is_completed ? (
          <Link
            to={deepLink.href}
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline print:hidden"
          >
            <ExternalLink className="h-3 w-3" aria-hidden />
            {deepLink.label}
          </Link>
        ) : null}
      </div>
    </li>
  );
}

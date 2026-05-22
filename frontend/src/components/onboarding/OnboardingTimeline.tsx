import { cn } from "@/lib/utils";
import type { TimelineMilestone } from "@/lib/onboardingUtils";

type OnboardingTimelineProps = {
  milestones: TimelineMilestone[];
};

const DOT_CLASS: Record<TimelineMilestone["status"], string> = {
  done: "bg-emerald-600 border-emerald-600",
  partial: "bg-amber-500 border-amber-500",
  pending: "bg-muted border-muted-foreground/30",
  overdue: "bg-destructive border-destructive",
};

export function OnboardingTimeline({ milestones }: OnboardingTimelineProps) {
  return (
    <div className="print:break-inside-avoid">
      <p className="mb-3 text-xs font-medium text-muted-foreground uppercase tracking-wide">
        Jalons d&apos;intégration
      </p>
      <div className="relative flex items-start justify-between gap-2">
        <div
          className="absolute left-[8%] right-[8%] top-3 h-0.5 bg-border"
          aria-hidden
        />
        {milestones.map((m) => (
          <div key={m.day} className="relative z-10 flex flex-1 flex-col items-center text-center">
            <div
              className={cn(
                "h-6 w-6 rounded-full border-2",
                DOT_CLASS[m.status],
              )}
              title={`${m.label} — ${m.completed}/${m.total} tâches`}
            />
            <span className="mt-2 text-xs font-semibold">{m.label}</span>
            <span className="mt-0.5 text-[10px] text-muted-foreground tabular-nums">
              {m.completed}/{m.total}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

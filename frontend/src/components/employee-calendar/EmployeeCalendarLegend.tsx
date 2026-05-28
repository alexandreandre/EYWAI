import { CALENDAR_LEGEND_ITEMS } from '@/lib/calendarTypes';
import { cn } from '@/lib/utils';

export function EmployeeCalendarLegend({ showPlanningPastille = false }: { showPlanningPastille?: boolean }) {
  return (
    <div className="space-y-3 border-t pt-4">
      <div className="flex flex-wrap gap-x-4 gap-y-2">
        {CALENDAR_LEGEND_ITEMS.map((item) => (
          <div key={item.key} className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className={cn('h-3 w-3 shrink-0 rounded-sm', item.colorClass)} aria-hidden />
            <span>{item.label}</span>
          </div>
        ))}
      </div>
      {showPlanningPastille && (
        <div className="flex flex-wrap gap-x-4 gap-y-2">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span
              className="h-3 min-w-[2rem] shrink-0 rounded-sm bg-violet-100 dark:bg-violet-950/50"
              aria-hidden
            />
            <span>Créneau planning publié</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span
              className="h-3 min-w-[2rem] shrink-0 rounded-sm border border-amber-400/80 bg-amber-50/90"
              aria-hidden
            />
            <span>Créneau sur jour non travaillé (paie)</span>
          </div>
        </div>
      )}
    </div>
  );
}

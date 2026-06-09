import { CALENDAR_LEGEND_ITEMS } from '@/lib/calendarTypes';
import { cn } from '@/lib/utils';

export function EmployeeCalendarLegend() {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-2 border-t pt-4">
      {CALENDAR_LEGEND_ITEMS.map((item) => (
        <div key={item.key} className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className={cn('h-3 w-3 shrink-0 rounded-sm', item.colorClass)} aria-hidden />
          <span>{item.label}</span>
        </div>
      ))}
    </div>
  );
}

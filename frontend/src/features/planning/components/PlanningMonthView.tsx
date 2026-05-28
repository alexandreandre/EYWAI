import { format, isSameMonth } from "date-fns";
import { Skeleton } from "@/components/ui/skeleton";
import type { Shift } from "@/api/planning";
import {
  apiErrorMessage,
  employeeShort,
  shiftBadgeBackground,
  shiftTypeShortLabel,
} from "@/features/planning/utils/planningUtils";

interface Props {
  monthAnchor: Date;
  monthCalendarRows: Date[][];
  monthShiftsByDay: Record<string, Shift[]>;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  onEditShift: (shift: Shift) => void;
}

export function PlanningMonthView({
  monthAnchor,
  monthCalendarRows,
  monthShiftsByDay,
  isLoading,
  isError,
  error,
  onEditShift,
}: Props) {
  return (
    <div className="space-y-3">
        <div className="space-y-3">
          {isLoading ? (
            <div className="space-y-2 rounded-md border p-4">
              <Skeleton className="h-8 w-48" />
              <Skeleton className="h-72 w-full" />
            </div>
          ) : isError ? (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
              {apiErrorMessage(error)}
            </div>
          ) : (
            <div className="w-full overflow-x-auto rounded-md border">
              <div className="w-full min-w-[720px] text-sm">
                <div className="grid grid-cols-7 border-b bg-muted/40">
                  {['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'].map((d, i) => (
                    <div
                      key={d}
                      className={`min-w-0 overflow-hidden px-2 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground ${
                        i < 6 ? 'border-r border-border' : ''
                      }`}
                    >
                      {d}
                    </div>
                  ))}
                </div>
                {monthCalendarRows.map((row, ri) => (
                  <div
                    key={ri}
                    className="grid grid-cols-7 border-b border-border last:border-b-0"
                  >
                    {row.map((cell, ci) => {
                      const iso = format(cell, 'yyyy-MM-dd');
                      const inMonth = isSameMonth(cell, monthAnchor);
                      const dayShifts = monthShiftsByDay[iso] ?? [];
                      const visible = dayShifts.slice(0, 3);
                      const more = dayShifts.length - visible.length;
                      return (
                        <div
                          key={iso}
                          className={`min-h-28 min-w-0 overflow-hidden px-1.5 py-2 align-top ${
                            ci < 6 ? 'border-r border-border' : ''
                          }`}
                        >
                          <div
                            className={`mb-1 text-xs font-semibold ${
                              inMonth ? 'text-foreground' : 'text-muted-foreground/60'
                            }`}
                          >
                            {format(cell, 'd')}
                          </div>
                          <div className="flex min-h-24 w-full min-w-0 flex-col gap-1 overflow-hidden">
                            {visible.map((s) => (
                              <button
                                key={s.id}
                                type="button"
                                className={`flex w-full min-w-0 max-w-full flex-col gap-0.5 rounded px-1.5 py-0.5 text-left text-xs font-medium text-white ring-1 ring-black/10 transition hover:opacity-95 ${
                                  s.is_locked ? 'cursor-not-allowed opacity-80' : ''
                                }`}
                                style={{ backgroundColor: shiftBadgeBackground(s) }}
                                disabled={s.is_locked}
                                onClick={() => {
                                  if (!s.is_locked) onEditShift(s);
                                }}
                                title={`${employeeShort(s)} — ${shiftTypeShortLabel(s)}`}
                              >
                                {s.is_replacement ? (
                                  <span className="inline-flex max-w-full shrink-0 self-start truncate rounded bg-orange-500 px-1 py-px text-[9px] font-bold uppercase leading-none text-white">
                                    Rempl.
                                  </span>
                                ) : null}
                                <span className="block w-full min-w-0 truncate">
                                  {employeeShort(s)} · {shiftTypeShortLabel(s)}
                                </span>
                                {s.is_replacement && s.original_employee_name ? (
                                  <span className="block w-full min-w-0 truncate text-[10px] font-normal opacity-95">
                                    Remplace {s.original_employee_name}
                                  </span>
                                ) : null}
                              </button>
                            ))}
                            {more > 0 ? (
                              <span className="w-full min-w-0 truncate text-xs text-muted-foreground">
                                +{more} autre{more > 1 ? 's' : ''}
                              </span>
                            ) : null}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

    </div>
  );
}

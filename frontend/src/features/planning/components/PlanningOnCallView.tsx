import { format, isSameMonth } from "date-fns";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { Shift } from "@/api/planning";
import { apiErrorMessage, employeeShort } from "@/features/planning/utils/planningUtils";

interface Props {
  isRH: boolean;
  monthAnchor: Date;
  monthCalendarRows: Date[][];
  onCallByDay: Record<string, Shift[]>;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  onAdd: () => void;
  onEditShift: (shift: Shift) => void;
}

export function PlanningOnCallView({
  isRH,
  monthAnchor,
  monthCalendarRows,
  onCallByDay,
  isLoading,
  isError,
  error,
  onAdd,
  onEditShift,
}: Props) {
  if (!isRH) {
    return (
      <div className="rounded-md border bg-muted/30 p-6 text-sm text-muted-foreground">
        La vue astreintes est réservée aux accès RH.
      </div>
    );
  }

  const totalOnCall = Object.values(onCallByDay).flat().length;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-lg font-semibold tracking-tight">Calendrier des astreintes</h2>
        <Button type="button" size="sm" onClick={onAdd}>
          <Plus className="mr-1 h-4 w-4" />
          Ajouter une astreinte
        </Button>
      </div>
      {isLoading ? (
        <div className="space-y-2 rounded-md border p-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : isError ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          {apiErrorMessage(error)}
        </div>
      ) : totalOnCall === 0 ? (
        <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
          Aucune astreinte sur ce mois.
        </div>
      ) : (
        <div className="w-full overflow-x-auto rounded-md border">
          <table className="w-full min-w-[720px] border-collapse text-sm">
            <thead>
              <tr className="border-b bg-muted/40">
                {['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'].map((d) => (
                  <th
                    key={d}
                    className="border-r px-2 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground last:border-r-0"
                  >
                    {d}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {monthCalendarRows.map((row, ri) => (
                <tr key={ri} className="border-b last:border-b-0">
                  {row.map((cell) => {
                    const iso = format(cell, 'yyyy-MM-dd');
                    const inMonth = isSameMonth(cell, monthAnchor);
                    const list = onCallByDay[iso] ?? [];
                    return (
                      <td key={iso} className="align-top border-r px-1.5 py-2 last:border-r-0">
                        <div
                          className={`mb-1 text-xs font-semibold ${
                            inMonth ? 'text-foreground' : 'text-muted-foreground/60'
                          }`}
                        >
                          {format(cell, 'd')}
                        </div>
                        <div className="flex min-h-[72px] flex-col gap-1">
                          {list.map((s) => (
                            <button
                              key={s.id}
                              type="button"
                              className="w-full truncate rounded-md border border-indigo-200/80 bg-indigo-100 px-2 py-1 text-left text-[11px] font-medium text-indigo-950 ring-1 ring-black/5 transition hover:bg-indigo-200 dark:border-indigo-800 dark:bg-indigo-950 dark:text-indigo-100 dark:hover:bg-indigo-900"
                              onClick={() => onEditShift(s)}
                              title="Voir / modifier"
                            >
                              {employeeShort(s)}
                            </button>
                          ))}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

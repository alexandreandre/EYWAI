import type { EmployeeHours, Shift } from '@/api/planning';
import { ShiftBlock } from '@/components/planning/ShiftBlock';

function formatMinutesLabel(totalMinutes: number): string {
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  return `${h}h${m.toString().padStart(2, '0')}`;
}

function formatDeltaBadge(delta: number): string {
  const sign = delta > 0 ? '+' : delta < 0 ? '-' : '';
  const abs = Math.abs(delta);
  const h = Math.floor(abs / 60);
  const m = abs % 60;
  return `${sign}${h.toString().padStart(2, '0')}h${m.toString().padStart(2, '0')}`;
}

export interface EmployeeRowProps {
  employee_id: string;
  first_name: string;
  last_name: string;
  contract_hours_per_week: number;
  shifts_by_day: Record<string, Shift[]>;
  hours_data: EmployeeHours;
  week_days: string[];
  onCellClick: (employee_id: string, date: string) => void;
  onShiftClick: (shift: Shift) => void;
  isWeekLocked: boolean;
  isRH: boolean;
}

export function EmployeeRow({
  employee_id,
  first_name,
  last_name,
  contract_hours_per_week,
  shifts_by_day,
  hours_data,
  week_days,
  onCellClick,
  onShiftClick,
  isWeekLocked,
  isRH,
}: EmployeeRowProps) {
  const delta = hours_data.delta;

  return (
    <tr className="border-b">
      <td className="sticky left-0 z-10 min-w-[160px] border-r bg-background px-2 py-2 align-top text-sm font-medium shadow-[2px_0_4px_-2px_rgba(0,0,0,0.08)]">
        <div>
          {last_name.toUpperCase()} {first_name}
        </div>
        <div className="mt-0.5 text-xs font-normal text-muted-foreground">
          Contrat : {contract_hours_per_week} h / sem.
        </div>
      </td>
      {week_days.map((d) => {
        const list = shifts_by_day[d] ?? [];
        return (
          <td
            key={d}
            className={`relative min-w-[100px] border-r px-1 py-1 align-top ${
              isRH && !isWeekLocked ? 'cursor-pointer hover:bg-accent' : ''
            }`}
            onClick={
              isRH && !isWeekLocked
                ? () => onCellClick(employee_id, d)
                : undefined
            }
          >
            <div className="pointer-events-none flex min-h-[72px] flex-col gap-1">
              {list.map((s) => (
                <div key={s.id} className="pointer-events-auto">
                  <ShiftBlock
                    shift={s}
                    onClick={onShiftClick}
                    isLocked={isWeekLocked || s.is_locked}
                  />
                </div>
              ))}
            </div>
          </td>
        );
      })}
      <td className="min-w-[100px] px-2 py-2 align-top text-sm">
        <div className="font-medium">{formatMinutesLabel(hours_data.total_minutes)}</div>
        {delta !== 0 ? (
          <div
            className={`mt-1 inline-block rounded px-1.5 py-0.5 text-xs font-semibold ${
              delta > 0
                ? 'bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-200'
                : 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-200'
            }`}
          >
            {formatDeltaBadge(delta)}
          </div>
        ) : null}
      </td>
    </tr>
  );
}

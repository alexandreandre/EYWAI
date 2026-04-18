import { useMemo } from 'react';
import { addDays, format, parseISO, startOfWeek } from 'date-fns';
import { fr } from 'date-fns/locale';
import type {
  EmployeeForPlanning,
  EmployeeHours,
  Shift,
  WeekPlanning,
} from '@/api/planning';
import { EmployeeRow } from '@/components/planning/EmployeeRow';
import { WeekHeader } from '@/components/planning/WeekHeader';

function normDay(d: string): string {
  return d.slice(0, 10);
}

function shiftDurationMinutes(s: Shift): number {
  const toSec = (t: string) => {
    const parts = t.split(':').map((x) => Number(x));
    return (parts[0] || 0) * 3600 + (parts[1] || 0) * 60 + (parts[2] || 0);
  };
  const a = toSec(s.start_time);
  let b = toSec(s.end_time);
  if (b <= a) {
    b += 24 * 3600;
  }
  return Math.round((b - a) / 60);
}

function buildWeekDays(weekStart: string, weekEnd: string): string[] {
  try {
    const start = parseISO(weekStart.slice(0, 10));
    const end = parseISO(weekEnd.slice(0, 10));
    const out: string[] = [];
    for (let d = start; d <= end; d = addDays(d, 1)) {
      out.push(format(d, 'yyyy-MM-dd'));
    }
    if (out.length === 7) {
      return out;
    }
  } catch {
    /* fallback */
  }
  const monday = startOfWeek(parseISO(weekStart.slice(0, 10)), { weekStartsOn: 1 });
  return Array.from({ length: 7 }, (_, i) => format(addDays(monday, i), 'yyyy-MM-dd'));
}

function dayLabel(iso: string): string {
  const d = parseISO(iso);
  return format(d, 'EEE dd/MM', { locale: fr }).replace(/^\w/, (c) => c.toUpperCase());
}

export interface WeekGridProps {
  planning: WeekPlanning;
  /** Salariés actifs (API). Si absent ou pas encore chargé, repli sur les shifts. */
  employees?: EmployeeForPlanning[];
  onCellClick: (employee_id: string, shift_date: string) => void;
  onShiftClick: (shift: Shift) => void;
  onLockDay: (day_date: string) => void;
  isRH: boolean;
  dayLocks?: Record<string, boolean>;
}

interface EmployeeRowModel {
  employee_id: string;
  first_name: string;
  last_name: string;
  contract_hours_per_week: number;
  shifts_by_day: Record<string, Shift[]>;
  hours_data: EmployeeHours;
}

export function WeekGrid({
  planning,
  employees: employeesFromApi,
  onCellClick,
  onShiftClick,
  onLockDay,
  isRH,
  dayLocks = {},
}: WeekGridProps) {
  const weekDays = useMemo(
    () => buildWeekDays(planning.week_start, planning.week_end),
    [planning.week_start, planning.week_end]
  );

  const employees = useMemo(() => {
    const shifts = planning.shifts ?? [];
    const hoursById = new Map(
      (planning.employee_hours ?? []).map((h) => [String(h.employee_id), h])
    );

    const useApiList =
      employeesFromApi !== undefined && employeesFromApi.length > 0;

    const map = new Map<string, EmployeeRowModel>();

    if (useApiList) {
      for (const emp of employeesFromApi) {
        const id = String(emp.id);
        const h = hoursById.get(id);
        const hours_data = h ?? undefined;
        const contract_minutes = Math.round(
          hours_data?.contract_minutes ??
            (emp.duree_hebdomadaire ?? 35) * 60
        );
        const hoursWeek = emp.duree_hebdomadaire ?? 35;
        map.set(id, {
          employee_id: id,
          first_name: emp.first_name ?? '',
          last_name: emp.last_name ?? '',
          contract_hours_per_week: hoursWeek,
          shifts_by_day: {},
          hours_data: {
            employee_id: id,
            total_minutes: 0,
            contract_minutes,
            delta: -contract_minutes,
          },
        });
      }
      for (const s of shifts) {
        const id = String(s.employee_id);
        const row = map.get(id);
        if (!row) continue;
        const day = normDay(s.shift_date);
        if (!row.shifts_by_day[day]) {
          row.shifts_by_day[day] = [];
        }
        row.shifts_by_day[day].push(s);
      }
    } else {
      for (const s of shifts) {
        const id = String(s.employee_id);
        if (!map.has(id)) {
          map.set(id, {
            employee_id: id,
            first_name: s.employee_first_name ?? '',
            last_name: s.employee_last_name ?? '',
            contract_hours_per_week: 35,
            shifts_by_day: {},
            hours_data: {
              employee_id: id,
              total_minutes: 0,
              contract_minutes: 35 * 60,
              delta: 0,
            },
          });
        }
        const row = map.get(id)!;
        const day = normDay(s.shift_date);
        if (!row.shifts_by_day[day]) {
          row.shifts_by_day[day] = [];
        }
        row.shifts_by_day[day].push(s);
      }
    }

    for (const row of map.values()) {
      const h = hoursById.get(row.employee_id);
      if (h) {
        row.hours_data = h;
        row.contract_hours_per_week = Math.round(h.contract_minutes / 60);
      } else {
        const total = Object.values(row.shifts_by_day)
          .flat()
          .filter((sh) => !sh.transverse_category)
          .reduce((acc, sh) => acc + shiftDurationMinutes(sh), 0);
        const contract_minutes = Math.round(row.contract_hours_per_week * 60);
        row.hours_data = {
          employee_id: row.employee_id,
          total_minutes: total,
          contract_minutes,
          delta: total - contract_minutes,
        };
      }
    }
    return Array.from(map.values()).sort((a, b) =>
      a.last_name.localeCompare(b.last_name, 'fr', { sensitivity: 'base' })
    );
  }, [planning.shifts, planning.employee_hours, employeesFromApi]);

  const { dayTotalsMinutes, dayStaffCount } = useMemo(() => {
    const totals: Record<string, number> = {};
    const staff: Record<string, Set<string>> = {};
    for (const d of weekDays) {
      totals[d] = 0;
      staff[d] = new Set();
    }
    for (const s of planning.shifts ?? []) {
      const d = normDay(s.shift_date);
      if (!(d in totals)) continue;
      totals[d] += shiftDurationMinutes(s);
      staff[d].add(s.employee_id);
    }
    const staffCount: Record<string, number> = {};
    for (const d of weekDays) {
      staffCount[d] = staff[d]?.size ?? 0;
    }
    return { dayTotalsMinutes: totals, dayStaffCount: staffCount };
  }, [planning.shifts, weekDays]);

  const isWeekLocked = planning.status === 'locked';
  const shiftList = planning.shifts ?? [];
  const noActiveEmployeesMessage =
    employeesFromApi !== undefined &&
    employeesFromApi.length === 0 &&
    shiftList.length === 0;

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full min-w-[960px] border-collapse text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="sticky left-0 z-20 min-w-[160px] border-r bg-muted/50 px-2 py-2 text-left font-semibold">
                Salarié
              </th>
              {weekDays.map((d) => (
                <th key={d} className="min-w-[110px] border-r px-1 py-1 text-left align-top">
                  <WeekHeader
                    date={d}
                    label={dayLabel(d)}
                    isLocked={Boolean(dayLocks[d])}
                    totalHours={(dayTotalsMinutes[d] ?? 0) / 60}
                    staffCount={dayStaffCount[d] ?? 0}
                    onLockDay={() => onLockDay(d)}
                    isRH={isRH}
                  />
                </th>
              ))}
              <th className="min-w-[100px] px-2 py-2 text-left font-semibold">Total sem.</th>
            </tr>
          </thead>
          <tbody>
            {employees.length === 0 ? (
              <tr>
                <td
                  colSpan={weekDays.length + 2}
                  className="px-4 py-8 text-center text-muted-foreground"
                >
                  {noActiveEmployeesMessage
                    ? 'Aucun salarié actif dans cette entreprise.'
                    : 'Chargement des salariés…'}
                </td>
              </tr>
            ) : (
              employees.map((emp) => (
                <EmployeeRow
                  key={emp.employee_id}
                  employee_id={emp.employee_id}
                  first_name={emp.first_name}
                  last_name={emp.last_name}
                  contract_hours_per_week={emp.contract_hours_per_week}
                  shifts_by_day={emp.shifts_by_day}
                  hours_data={emp.hours_data}
                  week_days={weekDays}
                  onCellClick={onCellClick}
                  onShiftClick={onShiftClick}
                  isWeekLocked={isWeekLocked}
                  isRH={isRH}
                />
              ))
            )}
          </tbody>
          <tfoot>
            <tr className="border-t bg-muted/30 font-medium">
              <td className="sticky left-0 z-10 border-r bg-muted/30 px-2 py-2">
                Total jour
              </td>
              {weekDays.map((d) => (
                <td key={d} className="border-r px-2 py-2 text-sm">
                  {((dayTotalsMinutes[d] ?? 0) / 60).toFixed(1)} h
                </td>
              ))}
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
      {isWeekLocked ? (
        <p className="text-center text-sm text-muted-foreground">
          Cette semaine est verrouillée. Déverrouillez pour modifier.
        </p>
      ) : null}
    </div>
  );
}

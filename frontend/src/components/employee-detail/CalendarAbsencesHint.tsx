import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getAbsencesForEmployee, type AbsenceRequest } from '@/api/absences';
import { Info } from 'lucide-react';

interface CalendarAbsencesHintProps {
  employeeId: string;
  year: number;
  month: number;
}

function absenceDaysInMonth(absences: AbsenceRequest[], year: number, month: number): number[] {
  const days = new Set<number>();
  const prefix = `${year}-${String(month).padStart(2, '0')}-`;

  for (const a of absences) {
    if (a.status !== 'validated') continue;
    for (const iso of a.selected_days ?? []) {
      if (iso.startsWith(prefix)) {
        const day = parseInt(iso.slice(8, 10), 10);
        if (!Number.isNaN(day)) days.add(day);
      }
    }
  }

  return [...days].sort((a, b) => a - b);
}

export function CalendarAbsencesHint({ employeeId, year, month }: CalendarAbsencesHintProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['employee-absences-calendar', employeeId],
    queryFn: async () => {
      const res = await getAbsencesForEmployee(employeeId);
      return res.data;
    },
    enabled: Boolean(employeeId),
    staleTime: 60_000,
  });

  const validatedDays = useMemo(
    () => (data ? absenceDaysInMonth(data, year, month) : []),
    [data, year, month]
  );

  if (isLoading || isError || validatedDays.length === 0) return null;

  return (
    <div className="mx-2 mb-2 flex items-start gap-2 rounded-md border border-blue-200/80 bg-blue-50/80 px-3 py-2 text-xs text-blue-900 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-100">
      <Info className="h-4 w-4 shrink-0 mt-0.5" />
      <p>
        <span className="font-medium">Absences validées (module Absences) :</span>{' '}
        jours {validatedDays.join(', ')} ce mois. Vérifiez la cohérence avec le calendrier paie
        (lecture seule).
      </p>
    </div>
  );
}

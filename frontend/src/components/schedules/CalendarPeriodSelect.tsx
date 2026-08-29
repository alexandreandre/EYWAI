import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

export const CALENDAR_MONTHS = [
  'Janvier',
  'Février',
  'Mars',
  'Avril',
  'Mai',
  'Juin',
  'Juillet',
  'Août',
  'Septembre',
  'Octobre',
  'Novembre',
  'Décembre',
] as const;

interface CalendarPeriodSelectProps {
  year: number;
  month: number;
  onYearChange: (year: number) => void;
  onMonthChange: (month: number) => void;
  /** Compact : sans libellés, pour la barre du planning. */
  compact?: boolean;
}

export function CalendarPeriodSelect({
  year,
  month,
  onYearChange,
  onMonthChange,
  compact = false,
}: CalendarPeriodSelectProps) {
  return (
    <div className="flex flex-wrap items-end gap-2">
      <div className={compact ? undefined : 'grid gap-1'}>
        {!compact && <Label className="text-xs">Mois</Label>}
        <Select value={String(month)} onValueChange={(v) => onMonthChange(Number(v))}>
          <SelectTrigger className="h-9 w-[140px]" aria-label="Mois">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CALENDAR_MONTHS.map((m, i) => (
              <SelectItem key={i} value={String(i + 1)}>
                {m}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className={compact ? undefined : 'grid gap-1'}>
        {!compact && <Label className="text-xs">Année</Label>}
        <Select value={String(year)} onValueChange={(v) => onYearChange(Number(v))}>
          <SelectTrigger className="h-9 w-[100px]" aria-label="Année">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {[year - 1, year, year + 1, year + 2].map((y) => (
              <SelectItem key={y} value={String(y)}>
                {y}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}

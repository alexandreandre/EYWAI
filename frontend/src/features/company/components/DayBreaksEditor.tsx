import { ChevronDown, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  computeBreakTotals,
  formatBreakSummary,
  grossPresenceHours,
  INDUSTRIAL_2X10_MEAL_30,
  type BreakKind,
  type DayBreak,
} from '@/lib/breakPolicy';

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  breaks: DayBreak[];
  onChange: (breaks: DayBreak[]) => void;
  hours: number;
  start: string;
  end: string;
  disabled?: boolean;
};

const KIND_LABELS: Record<BreakKind, string> = {
  short: 'Courte',
  meal: 'Repas',
  other: 'Autre',
};

export function DayBreaksEditor({
  open,
  onOpenChange,
  breaks,
  onChange,
  hours,
  start,
  end,
  disabled,
}: Props) {
  const { paid, unpaid } = computeBreakTotals(breaks);
  const grossNet = grossPresenceHours(start, end, unpaid);
  const hoursMismatch =
    grossNet !== null && Math.abs(grossNet - hours) > 5 / 60;

  const setBreak = (idx: number, patch: Partial<DayBreak>) => {
    onChange(breaks.map((b, i) => (i === idx ? { ...b, ...patch } : b)));
  };

  return (
    <div className="mt-2 rounded-md border bg-muted/20 p-2">
      <button
        type="button"
        className="flex w-full items-center gap-1 text-left text-xs font-medium text-muted-foreground"
        onClick={() => onOpenChange(!open)}
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        Détail des pauses — {formatBreakSummary(breaks)}
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {breaks.map((b, idx) => (
            <div key={idx} className="flex flex-wrap items-center gap-2">
              <Input
                type="number"
                className="h-8 w-16"
                min={0}
                disabled={disabled}
                value={b.minutes}
                onChange={(e) =>
                  setBreak(idx, { minutes: Number(e.target.value) || 0 })
                }
              />
              <span className="text-xs text-muted-foreground">min</span>
              <Select
                value={b.kind}
                disabled={disabled}
                onValueChange={(kind) => setBreak(idx, { kind: kind as BreakKind })}
              >
                <SelectTrigger className="h-8 w-28">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(KIND_LABELS).map(([k, label]) => (
                    <SelectItem key={k} value={k}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <label className="flex items-center gap-1 text-xs">
                <Checkbox
                  checked={b.paid}
                  disabled={disabled}
                  onCheckedChange={(v) => setBreak(idx, { paid: Boolean(v) })}
                />
                Payée
              </label>
              {breaks.length > 1 && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-8 px-2 text-xs"
                  disabled={disabled}
                  onClick={() => onChange(breaks.filter((_, i) => i !== idx))}
                >
                  Retirer
                </Button>
              )}
            </div>
          ))}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={disabled}
              onClick={() =>
                onChange([
                  ...breaks,
                  { minutes: 10, paid: false, kind: 'meal' },
                ])
              }
            >
              + Pause
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={disabled}
              onClick={() => onChange(INDUSTRIAL_2X10_MEAL_30.map((b) => ({ ...b })))}
            >
              Industriel 2×10 + repas 30
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Net {hours} h · Payées {paid} min · Repas {unpaid} min
            {grossNet !== null ? ` · Présence brute ≈ ${(grossNet + unpaid / 60).toFixed(2)} h` : ''}
          </p>
          {hoursMismatch && (
            <p className="text-xs text-amber-700">
              Écart horaires : fin − début − repas ({grossNet?.toFixed(2)} h) ≠ heures nettes (
              {hours} h).
            </p>
          )}
        </div>
      )}
    </div>
  );
}

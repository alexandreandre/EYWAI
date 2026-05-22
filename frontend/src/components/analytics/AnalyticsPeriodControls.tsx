import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  clampWeekForYear,
  currentPeriodPreset,
  formatMonthFr,
  isCurrentPeriodPreset,
  shiftPeriod,
  type PeriodGranularity,
  type PeriodSelection,
  weekOptionsForYear,
  yearOptions,
} from "@/lib/analyticsPeriod";
import { cn } from "@/lib/utils";

type AnalyticsPeriodControlsProps = {
  value: PeriodSelection;
  onChange: (next: PeriodSelection) => void;
  periodLabel: string;
  hint?: string | null;
  className?: string;
};

const GRANULARITY_OPTIONS: { value: PeriodGranularity; label: string } = [
  { value: "weekly", label: "Semaine" },
  { value: "monthly", label: "Mois" },
  { value: "annual", label: "Année" },
];

const PRESET_LABELS: Record<PeriodGranularity, string> = {
  weekly: "Cette semaine",
  monthly: "Ce mois",
  annual: "Cette année",
};

export function AnalyticsPeriodControls({
  value,
  onChange,
  periodLabel,
  hint,
  className,
}: AnalyticsPeriodControlsProps): JSX.Element {
  const years = yearOptions(6);
  const weeks = weekOptionsForYear(value.year);
  const atCurrent = isCurrentPeriodPreset(value);

  const setGranularity = (g: PeriodGranularity) => {
    if (g === value.granularity) return;
    onChange(currentPeriodPreset(g));
  };

  return (
    <div
      className={cn("flex w-full flex-col gap-2", className)}
      role="group"
      aria-label="Filtrer par période"
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        {/* Granularité : pills compacts (DA Planning / dashboard) */}
        <ToggleGroup
          type="single"
          value={value.granularity}
          onValueChange={(v) => {
            if (v === "weekly" || v === "monthly" || v === "annual") {
              setGranularity(v);
            }
          }}
          className="inline-flex h-9 w-full shrink-0 rounded-md border bg-muted/50 p-0.5 sm:w-auto"
        >
          {GRANULARITY_OPTIONS.map((opt) => (
            <ToggleGroupItem
              key={opt.value}
              value={opt.value}
              className={cn(
                "h-8 flex-1 rounded-sm px-3 text-xs font-medium sm:flex-none sm:px-4",
                "data-[state=on]:bg-background data-[state=on]:text-foreground data-[state=on]:shadow-sm",
                "data-[state=off]:text-muted-foreground",
              )}
              aria-label={opt.label}
            >
              {opt.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>

        {/* Navigation + sélecteurs contextuels */}
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2 lg:justify-end">
          <div className="flex min-w-0 flex-1 items-center gap-1.5 sm:flex-none">
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="h-9 w-9 shrink-0"
              onClick={() => onChange(shiftPeriod(value, -1))}
              aria-label="Période précédente"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>

            <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5 sm:flex-initial">
              {value.granularity === "weekly" ? (
                <>
                  <Select
                    value={String(value.week)}
                    onValueChange={(v) =>
                      onChange({ ...value, week: Number(v) })
                    }
                  >
                    <SelectTrigger
                      className="h-9 min-w-0 flex-1 sm:w-[min(220px,42vw)]"
                      aria-label="Semaine"
                    >
                      <SelectValue placeholder="Semaine" />
                    </SelectTrigger>
                    <SelectContent className="max-h-72">
                      {weeks.map((w) => (
                        <SelectItem key={w.week} value={String(w.week)}>
                          {w.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select
                    value={String(value.year)}
                    onValueChange={(v) => {
                      const y = Number(v);
                      onChange({
                        ...value,
                        year: y,
                        week: clampWeekForYear(y, value.week),
                      });
                    }}
                  >
                    <SelectTrigger className="h-9 w-[5.5rem] shrink-0" aria-label="Année">
                      <SelectValue placeholder="Année" />
                    </SelectTrigger>
                    <SelectContent>
                      {years.map((y) => (
                        <SelectItem key={y} value={String(y)}>
                          {y}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </>
              ) : null}

              {value.granularity === "monthly" ? (
                <>
                  <Select
                    value={String(value.month)}
                    onValueChange={(v) =>
                      onChange({ ...value, month: Number(v) })
                    }
                  >
                    <SelectTrigger
                      className="h-9 w-[min(9.5rem,38vw)] shrink-0"
                      aria-label="Mois"
                    >
                      <SelectValue placeholder="Mois" />
                    </SelectTrigger>
                    <SelectContent>
                      {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                        <SelectItem key={m} value={String(m)}>
                          {formatMonthFr(m)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select
                    value={String(value.year)}
                    onValueChange={(v) =>
                      onChange({ ...value, year: Number(v) })
                    }
                  >
                    <SelectTrigger className="h-9 w-[5.5rem] shrink-0" aria-label="Année">
                      <SelectValue placeholder="Année" />
                    </SelectTrigger>
                    <SelectContent>
                      {years.map((y) => (
                        <SelectItem key={y} value={String(y)}>
                          {y}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </>
              ) : null}

              {value.granularity === "annual" ? (
                <Select
                  value={String(value.year)}
                  onValueChange={(v) =>
                    onChange({ ...value, year: Number(v) })
                  }
                >
                  <SelectTrigger
                    className="h-9 w-[min(8rem,32vw)] shrink-0"
                    aria-label="Année"
                  >
                    <SelectValue placeholder="Année" />
                  </SelectTrigger>
                  <SelectContent>
                    {years.map((y) => (
                      <SelectItem key={y} value={String(y)}>
                        {y}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : null}
            </div>

            <Button
              type="button"
              variant="outline"
              size="icon"
              className="h-9 w-9 shrink-0"
              onClick={() => onChange(shiftPeriod(value, 1))}
              aria-label="Période suivante"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>

          <span
            className="hidden min-w-0 truncate text-sm font-medium text-foreground xl:inline xl:max-w-[14rem]"
            title={periodLabel}
          >
            {periodLabel}
          </span>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-9 shrink-0 text-xs"
            disabled={atCurrent}
            onClick={() => onChange(currentPeriodPreset(value.granularity))}
          >
            {PRESET_LABELS[value.granularity]}
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
        <span className="font-medium text-foreground xl:hidden">{periodLabel}</span>
        {hint ? <span className="text-muted-foreground">· {hint}</span> : null}
      </div>
    </div>
  );
}

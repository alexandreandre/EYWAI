// src/components/CalendarDayCell.tsx

import { useState, useEffect, useRef } from 'react';
import { DayCellContentArg } from '@fullcalendar/core';
import { PlannedEventData, ActualHoursData } from '@/api/calendar';
import { DayData } from '@/components/ScheduleModal';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import { Calendar, Clock, Copy } from 'lucide-react';
import { isFrenchPublicHoliday } from '@/lib/frenchPublicHolidays';
import {
  CALENDAR_TYPE_BAR_COLORS,
  getCalendarTypeLabel,
} from '@/lib/calendarTypes';
import { isDayReadyForPayroll } from '@/lib/calendarStats';

interface CalendarDayCellProps {
  arg: DayCellContentArg;
  plannedCalendar: PlannedEventData[];
  actualHours: ActualHoursData[];
  updateDayData: (day: Partial<DayData>) => void;
  selectedDays?: number[];
  onDaySelect?: (dayNumber: number) => void;
  selectedDate: { month: number; year: number };
  isForfaitJour?: boolean;
  onCopyPlannedToActual?: (dayNumber: number) => void;
}

const EDITABLE_TYPES = [
  { value: 'travail', label: 'Travail' },
  { value: 'conge', label: 'Congé' },
  { value: 'ferie', label: 'Férié' },
  { value: 'arret_maladie', label: 'Arrêt maladie' },
  { value: 'weekend', label: 'Week-end' },
] as const;

const DEFAULT_SCALE_HOURS = 10;

function dayNeedsInput(
  type: string,
  plannedDay: PlannedEventData,
  actualDay: ActualHoursData,
  isForfaitJour = false
): boolean {
  if (type !== 'travail') return false;
  return !isDayReadyForPayroll(plannedDay, actualDay, isForfaitJour);
}

function HourGauges({
  planned,
  actual,
  isForfaitJour,
}: {
  planned: number | null | undefined;
  actual: number | null | undefined;
  isForfaitJour: boolean;
}) {
  const hasPlanned = planned !== null && planned !== undefined;
  const hasActual = actual !== null && actual !== undefined;

  if (!hasPlanned && !hasActual) {
    return (
      <p className="text-[10px] text-muted-foreground/80 italic px-2 pl-3 pb-2">
        Aucune saisie
      </p>
    );
  }

  if (isForfaitJour) {
    const pVal = hasPlanned ? (planned === 1 ? 1 : 0) : null;
    const aVal = hasActual ? (actual === 1 ? 1 : 0) : null;
    return (
      <div className="flex flex-col gap-2 flex-1 px-2 pl-3 pb-2.5">
        <DayGaugeRow
          label="Prévu"
          value={pVal}
          filled={pVal === 1}
          barClass="bg-sky-500"
          trackClass="bg-sky-100"
          textClass="text-sky-800"
          unit="jour"
        />
        <DayGaugeRow
          label="Réel"
          value={aVal}
          filled={aVal === 1}
          barClass="bg-teal-500"
          trackClass="bg-teal-100"
          textClass="text-teal-800"
          unit="jour"
        />
      </div>
    );
  }

  const p = hasPlanned ? planned! : 0;
  const a = hasActual ? actual! : 0;
  const max = Math.max(DEFAULT_SCALE_HOURS, p, a, 1);
  const pPct = hasPlanned ? Math.min(100, (p / max) * 100) : 0;
  const aPct = hasActual ? Math.min(100, (a / max) * 100) : 0;

  return (
    <div className="flex flex-col gap-2 flex-1 px-2 pl-3 pb-2.5">
      <DayGaugeRow
        label="Prévu"
        value={hasPlanned ? p : null}
        percent={pPct}
        barClass="bg-sky-500"
        trackClass="bg-sky-100/90"
        textClass="text-sky-800 dark:text-sky-300"
        unit="h"
        showBar
      />
      <DayGaugeRow
        label="Réel"
        value={hasActual ? a : null}
        percent={aPct}
        barClass="bg-teal-500"
        trackClass="bg-teal-100/90"
        textClass="text-teal-800 dark:text-teal-300"
        unit="h"
        showBar
      />
    </div>
  );
}

function DayGaugeRow({
  label,
  value,
  filled,
  percent = 0,
  barClass,
  trackClass,
  textClass,
  unit,
  showBar = false,
}: {
  label: string;
  value: number | null;
  filled?: boolean;
  percent?: number;
  barClass: string;
  trackClass: string;
  textClass: string;
  unit: string;
  showBar?: boolean;
}) {
  const display =
    value === null
      ? '–'
      : unit === 'jour'
        ? value === 1
          ? 'Oui'
          : 'Non'
        : `${value}${unit === 'h' ? ' h' : ''}`;

  const barWidth = showBar ? percent : filled ? 100 : 0;

  return (
    <div className="space-y-0.5">
      <div className="flex items-baseline justify-between gap-1">
        <span className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <span className={cn('text-base font-bold tabular-nums leading-none', textClass)}>
          {display}
        </span>
      </div>
      <div className={cn('h-3 w-full rounded-full overflow-hidden shadow-inner', trackClass)}>
        <div
          className={cn('h-full rounded-full transition-all duration-300', barClass)}
          style={{ width: `${barWidth}%` }}
        />
      </div>
    </div>
  );
}

export function CalendarDayCell({
  arg,
  plannedCalendar,
  actualHours,
  updateDayData,
  selectedDays = [],
  onDaySelect,
  selectedDate,
  isForfaitJour = false,
  onCopyPlannedToActual,
}: CalendarDayCellProps) {
  const dayNumber = arg.date.getDate();
  const cellRef = useRef<HTMLDivElement>(null);
  const plannedInputRef = useRef<HTMLInputElement>(null);
  const actualInputRef = useRef<HTMLInputElement>(null);

  const plannedDay = plannedCalendar.find((d) => d.jour === dayNumber);
  const actualDay = actualHours.find((d) => d.jour === dayNumber);

  const isCurrentMonth =
    arg.date.getMonth() + 1 === selectedDate.month &&
    arg.date.getFullYear() === selectedDate.year;

  const [isEditing, setIsEditing] = useState(false);
  const [typePopoverOpen, setTypePopoverOpen] = useState(false);

  const isToday = arg.isToday;
  const isSelected = isCurrentMonth && selectedDays.includes(dayNumber);
  const isHoliday = isFrenchPublicHoliday(
    selectedDate.year,
    selectedDate.month,
    dayNumber
  );

  const hasHourValues =
    (plannedDay?.heures_prevues !== null && plannedDay?.heures_prevues !== undefined) ||
    (actualDay?.heures_faites !== null && actualDay?.heures_faites !== undefined);

  useEffect(() => {
    if (isToday && isCurrentMonth && cellRef.current) {
      cellRef.current.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [isToday, isCurrentMonth, selectedDate.month, selectedDate.year]);

  useEffect(() => {
    if (isEditing && !isForfaitJour) {
      const t = window.setTimeout(() => {
        plannedInputRef.current?.focus();
        plannedInputRef.current?.select();
      }, 0);
      return () => window.clearTimeout(t);
    }
  }, [isEditing, isForfaitJour]);

  const commitHourEditing = () => {
    setIsEditing(false);
    plannedInputRef.current?.blur();
    actualInputRef.current?.blur();
  };

  const handleEditingKeyDownCapture = (e: React.KeyboardEvent) => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    e.stopPropagation();
    commitHourEditing();
  };

  if (!isCurrentMonth) {
    return (
      <div className="flex h-full items-start justify-start p-2">
        <span className="text-muted-foreground/30">{arg.dayNumberText}</span>
      </div>
    );
  }

  if (!plannedDay || !actualDay) {
    return (
      <div className="flex h-full items-start justify-start p-2">
        <span className="text-muted-foreground">{arg.dayNumberText}</span>
      </div>
    );
  }

  const needsInput = dayNeedsInput(plannedDay.type, plannedDay, actualDay, isForfaitJour);

  const handleTypeChange = (newType: string) => {
    const preserved = plannedDay.heures_prevues;
    let defaultHours: number | null = preserved ?? null;

    if (preserved === null || preserved === undefined) {
      if (isForfaitJour) {
        defaultHours = newType === 'travail' ? 1 : 0;
      } else if (newType === 'travail') {
        defaultHours = 8;
      }
    }

    updateDayData({
      jour: dayNumber,
      type: newType,
      heures_prevues: defaultHours,
    });
    setTypePopoverOpen(false);
  };

  const barColor = CALENDAR_TYPE_BAR_COLORS[plannedDay.type] ?? 'bg-gray-300';

  return (
    <div
      ref={cellRef}
      className={cn(
        'group relative flex h-full min-h-[7.5rem] w-full flex-col rounded-2xl border bg-card transition-all duration-200',
        'hover:shadow-md',
        isSelected && 'ring-2 ring-primary ring-offset-1',
        isToday && 'ring-2 ring-primary/60',
        needsInput && 'border-dashed border-amber-400/80',
        hasHourValues && !isEditing && 'border-sky-200/60 bg-gradient-to-b from-card to-sky-50/30 dark:to-sky-950/20',
        isEditing && 'ring-1 ring-primary shadow-md z-10'
      )}
      onClick={() => setIsEditing(true)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) {
          setIsEditing(false);
        }
      }}
    >
      <div className={cn('absolute left-0 top-2 bottom-2 w-1.5 rounded-full', barColor)} />

      <div className="flex items-start justify-between gap-1 p-2 pl-3 shrink-0">
        <div className="flex flex-col min-w-0">
          <span
            className={cn(
              'text-xs font-semibold tabular-nums',
              isToday && 'text-primary'
            )}
          >
            {arg.dayNumberText}
          </span>
          {isToday && (
            <span className="text-[9px] font-medium text-primary leading-none">Aujourd&apos;hui</span>
          )}
        </div>

        <div className="flex items-center gap-0.5">
          {onCopyPlannedToActual && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
              title="Coller le prévu en réel"
              onClick={(e) => {
                e.stopPropagation();
                onCopyPlannedToActual(dayNumber);
              }}
            >
              <Copy className="h-3 w-3" />
            </Button>
          )}
          <Checkbox
            checked={isSelected}
            onCheckedChange={() => onDaySelect?.(dayNumber)}
            aria-label={`Sélectionner le jour ${dayNumber}`}
            className="h-4 w-4"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      </div>

      <div className="px-2 pl-3 pb-1 shrink-0">
        <Popover open={typePopoverOpen} onOpenChange={setTypePopoverOpen}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="text-[10px] font-medium text-muted-foreground hover:text-foreground truncate max-w-full text-left"
              onClick={(e) => {
                e.stopPropagation();
                setTypePopoverOpen(true);
              }}
            >
              {getCalendarTypeLabel(plannedDay.type)}
              {isHoliday && plannedDay.type !== 'ferie' && (
                <span className="text-purple-600 ml-0.5">(férié)</span>
              )}
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-40 p-1" align="start" onClick={(e) => e.stopPropagation()}>
            {EDITABLE_TYPES.map((t) => (
              <button
                key={t.value}
                type="button"
                className={cn(
                  'w-full text-left text-xs px-2 py-1.5 rounded hover:bg-muted',
                  plannedDay.type === t.value && 'bg-muted font-medium'
                )}
                onClick={() => handleTypeChange(t.value)}
              >
                {t.label}
              </button>
            ))}
          </PopoverContent>
        </Popover>
      </div>

      {isEditing ? (
        <div
          className="flex flex-col gap-1.5 px-2 pl-3 pb-2 flex-1"
          onClick={(e) => e.stopPropagation()}
          onKeyDownCapture={handleEditingKeyDownCapture}
        >
          {isForfaitJour ? (
            <>
              <label className="flex items-center gap-2 text-xs">
                <Checkbox
                  checked={plannedDay.heures_prevues === 1}
                  onCheckedChange={(c) =>
                    updateDayData({
                      jour: dayNumber,
                      heures_prevues: c === true ? 1 : 0,
                    })
                  }
                  className="h-3.5 w-3.5"
                />
                Jour prévu
              </label>
              <label className="flex items-center gap-2 text-xs">
                <Checkbox
                  checked={actualDay.heures_faites === 1}
                  onCheckedChange={(c) =>
                    updateDayData({
                      jour: dayNumber,
                      heures_faites: c === true ? 1 : 0,
                    })
                  }
                  className="h-3.5 w-3.5"
                />
                Jour travaillé
              </label>
            </>
          ) : (
            <>
              <div className="relative flex items-center">
                <Calendar className="absolute left-1 h-3 w-3 text-sky-600" />
                <Input
                  ref={plannedInputRef}
                  type="number"
                  min={0}
                  step={0.5}
                  placeholder="H. prévues"
                  value={plannedDay.heures_prevues ?? ''}
                  onChange={(e) =>
                    updateDayData({
                      jour: dayNumber,
                      heures_prevues: e.target.value ? parseFloat(e.target.value) : null,
                    })
                  }
                  className="h-8 text-sm pl-5 font-medium"
                />
              </div>
              <div className="relative flex items-center">
                <Clock className="absolute left-1 h-3 w-3 text-teal-600" />
                <Input
                  ref={actualInputRef}
                  type="number"
                  min={0}
                  step={0.5}
                  placeholder="H. faites"
                  value={actualDay.heures_faites ?? ''}
                  onChange={(e) =>
                    updateDayData({
                      jour: dayNumber,
                      heures_faites: e.target.value ? parseFloat(e.target.value) : null,
                    })
                  }
                  className="h-8 text-sm pl-5 font-medium"
                />
              </div>
            </>
          )}
        </div>
      ) : (
        <HourGauges
          planned={plannedDay.heures_prevues}
          actual={actualDay.heures_faites}
          isForfaitJour={isForfaitJour}
        />
      )}
    </div>
  );
}

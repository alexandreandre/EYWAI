// src/components/CalendarDayCell.tsx

import { useState, useEffect, useRef } from 'react';
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
import { shouldShowHolidayHint } from '@/lib/companyCalendarHolidays';
import { useObservedPublicHolidays } from '@/hooks/useObservedPublicHolidays';
import {
  CALENDAR_TYPE_BAR_COLORS,
  CALENDAR_TYPE_BG_COLORS,
  COULEUR_PREVU,
  COULEUR_REEL,
  editableTypeOptionsFor,
  getCalendarTypeLabel,
} from '@/lib/calendarTypes';
import { isDayReadyForPayroll } from '@/lib/calendarStats';
import { estAbsentATyper } from '@/lib/absentATyper';
import { libelleApresSortie } from '@/lib/employmentStatus';
import {
  TITRE_INFO_BULLE_CONFLIT,
  estJourEnConflit,
} from '@/features/payroll/utils/heuresSurArret';

/** Jour de la grille du mois, construit par l'écran qui affiche la cellule. */
interface JourDeLaGrille {
  date: Date;
  dayNumberText: string;
  isToday: boolean;
}

interface CalendarDayCellProps {
  arg: JourDeLaGrille;
  plannedCalendar: PlannedEventData[];
  actualHours: ActualHoursData[];
  updateDayData: (day: Partial<DayData> & { demi_journee?: 'matin' | 'apres_midi' | null }) => void;
  selectedDays?: number[];
  onDaySelect?: (dayNumber: number) => void;
  selectedDate: { month: number; year: number };
  isForfaitJour?: boolean;
  onCopyPlannedToActual?: (dayNumber: number) => void;
  /** Jours en conflit dits par le backend (heures saisies pendant un arrêt ou une absence). */
  joursEnConflit?: number[];
  /** Le salarié pointe sur la période (`useCalendar`). Faux : un jour sans réel n'attend rien. */
  pointe?: boolean;
  /**
   * Dernier jour jugé (fin de la fenêtre des variables ou sortie) : après, un
   * jour vide n'est pas signalé à saisir, il appartient au mois suivant.
   */
  dernierJourJuge?: number | null;
  /** Dernier jour du contrat (sortie) : après, la case est grisée et fermée. */
  dernierJourContrat?: number | null;
}

// Types de saisie : source unique calendarTypes.ts — conges_payes/rtt créent
// automatiquement la demande validée côté serveur ; l'ancien « conge » (hors
// paie) n'est proposé que si le jour le porte déjà (retypage historique).

const DEFAULT_SCALE_HOURS = 10;

/** Infobulle d'un jour coché « absent » à l'import, sans type encore. */
const TITRE_ABSENT_A_TYPER =
  'Absent : donnez le type du jour (congé, RTT, arrêt ou absence non payée). La paie reste bloquée tant qu’il manque.';

function dayNeedsInput(
  type: string,
  plannedDay: PlannedEventData,
  actualDay: ActualHoursData,
  isForfaitJour = false,
  pointe = true
): boolean {
  if (type !== 'travail') return false;
  return !isDayReadyForPayroll(plannedDay, actualDay, isForfaitJour, pointe);
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
    // Une quantité positive vaut un jour, en jours (1) comme en heures (7,8)
    // (retour du 10/11 : prévu en heures, réel en jours).
    const pVal = hasPlanned ? (Number(planned) > 0 ? 1 : 0) : null;
    const aVal = hasActual ? (Number(actual) > 0 ? 1 : 0) : null;
    return (
      <div className="flex flex-col gap-2 flex-1 px-2 pl-3 pb-2.5">
        <DayGaugeRow
          label="Prévu"
          value={pVal}
          filled={pVal === 1}
          barClass={COULEUR_PREVU.barre}
          trackClass={COULEUR_PREVU.piste}
          textClass={COULEUR_PREVU.texte}
          unit="forfait"
        />
        <DayGaugeRow
          label="Travaillé"
          value={aVal}
          filled={aVal === 1}
          barClass={COULEUR_REEL.barre}
          trackClass={COULEUR_REEL.piste}
          textClass={COULEUR_REEL.texte}
          unit="forfait"
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
        barClass={COULEUR_PREVU.barre}
        trackClass={COULEUR_PREVU.piste}
        textClass={`${COULEUR_PREVU.texte} ${COULEUR_PREVU.texteSombre}`}
        unit="h"
        showBar
      />
      <DayGaugeRow
        label="Réel"
        value={hasActual ? a : null}
        percent={aPct}
        barClass={COULEUR_REEL.barre}
        trackClass={COULEUR_REEL.piste}
        textClass={`${COULEUR_REEL.texte} ${COULEUR_REEL.texteSombre}`}
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
      ? unit === 'forfait'
        ? ''
        : '–'
      : unit === 'forfait'
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
  joursEnConflit,
  pointe = true,
  dernierJourJuge = null,
  dernierJourContrat = null,
}: CalendarDayCellProps) {
  const { observedHolidayIds } = useObservedPublicHolidays();
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
  const showHolidayHint =
    isCurrentMonth &&
    plannedDay != null &&
    shouldShowHolidayHint(
      selectedDate.year,
      selectedDate.month,
      dayNumber,
      plannedDay.type,
      observedHolidayIds
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
        const input = plannedDay?.type === 'repos' ? actualInputRef.current : plannedInputRef.current;
        input?.focus();
        input?.select();
      }, 0);
      return () => window.clearTimeout(t);
    }
  }, [isEditing, isForfaitJour, plannedDay?.type]);

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

  // Après la sortie : rien à saisir, la case est grisée et fermée (retour du 10/11).
  if (dernierJourContrat != null && dayNumber > dernierJourContrat) {
    return (
      <div
        className="flex h-full min-h-[7.5rem] flex-col gap-1 rounded-2xl border bg-muted/50 p-2 text-muted-foreground/70"
        title={libelleApresSortie(dernierJourContrat, selectedDate.month)}
        data-testid="case-apres-sortie"
      >
        <span className="text-xs font-semibold tabular-nums">{arg.dayNumberText}</span>
        <span className="text-[10px]">Sorti(e) · 0 h</span>
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

  // Après l'arrêté des variables, le jour compte pour le mois suivant : pas
  // d'anomalie ici (retour du 10/11).
  const needsInput =
    (dernierJourJuge == null || dayNumber <= dernierJourJuge) &&
    dayNeedsInput(plannedDay.type, plannedDay, actualDay, isForfaitJour, pointe);

  const handleTypeChange = (
    newType: string,
    demiJournee: 'matin' | 'apres_midi' | null = null
  ) => {
    const preserved = plannedDay.heures_prevues;
    let defaultHours: number | null = preserved ?? null;

    if (preserved === null || preserved === undefined) {
      if (isForfaitJour) {
        defaultHours = newType === 'travail' ? 1 : 0;
      } else if (newType === 'travail') {
        defaultHours = 8;
      }
    }
    if (newType === 'conges_payes' || newType === 'rtt' || newType === 'repos') {
      // Jour d'absence : 0 h au planning (convention bulletin) — la demande
      // validée créée côté serveur porte le décompte CP/RTT. Un repos n'en
      // crée aucune : la récupération éventuelle est suivie à l'extérieur.
      defaultHours = 0;
    }

    updateDayData({
      jour: dayNumber,
      type: newType,
      heures_prevues: defaultHours,
      ...(newType === 'conges_payes' || newType === 'rtt' ? { demi_journee: demiJournee } : {}),
    });
    setTypePopoverOpen(false);
  };

  const barColor = CALENDAR_TYPE_BAR_COLORS[plannedDay.type] ?? 'bg-gray-300';
  // Fond teinté par type : mêmes couleurs que la vue semaine équipe
  // (congé vert, arrêt rouge…) pour vérifier d'un coup d'œil.
  const bgColor = CALENDAR_TYPE_BG_COLORS[plannedDay.type] ?? 'bg-card';
  const enConflit = estJourEnConflit(dayNumber, joursEnConflit);
  const absent = estAbsentATyper(plannedDay);
  const infoBulle = enConflit ? TITRE_INFO_BULLE_CONFLIT : absent ? TITRE_ABSENT_A_TYPER : undefined;

  return (
    <div
      ref={cellRef}
      title={infoBulle}
      data-conflit-arret={enConflit ? 'true' : undefined}
      data-absent-a-typer={absent ? 'true' : undefined}
      className={cn(
        'group relative flex h-full min-h-[7.5rem] w-full flex-col rounded-2xl border transition-all duration-200',
        enConflit ? 'bg-rose-100 border-rose-400 ring-2 ring-rose-400' : bgColor,
        'hover:shadow-md',
        isSelected && 'ring-2 ring-primary ring-offset-1',
        isToday && 'ring-2 ring-primary/60',
        needsInput && 'border-dashed border-amber-400/80',
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
      {enConflit && <span className="sr-only">{TITRE_INFO_BULLE_CONFLIT}</span>}
      {absent && !enConflit && <span className="sr-only">{TITRE_ABSENT_A_TYPER}</span>}

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
              {showHolidayHint && (
                <span className="text-purple-600 ml-0.5">(férié)</span>
              )}
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-40 p-1" align="start" onClick={(e) => e.stopPropagation()}>
            {absent && (
              <p
                className="mb-1 rounded bg-red-50 px-2 py-1 text-[11px] font-medium text-red-800"
                data-testid="choisir-type-absence"
              >
                Choisissez le type de l’absence.
              </p>
            )}
            {editableTypeOptionsFor(plannedDay.type).map((t) => (
              <div key={t.value}>
                <button
                  type="button"
                  className={cn(
                    'w-full text-left text-xs px-2 py-1.5 rounded hover:bg-muted',
                    plannedDay.type === t.value && 'bg-muted font-medium'
                  )}
                  onClick={() => handleTypeChange(t.value)}
                >
                  {t.label}
                </button>
                {/* Demi-journée, comme dans « Saisir les congés » (retour du 10/11). */}
                {!isForfaitJour &&
                  (t.value === 'conges_payes' || t.value === 'rtt') &&
                  plannedDay.type !== t.value && (
                    <div className="flex gap-1 pl-3 pb-1">
                      {(
                        [
                          ['matin', 'matin'],
                          ['apres_midi', 'après-midi'],
                        ] as const
                      ).map(([valeur, libelle]) => (
                        <button
                          key={valeur}
                          type="button"
                          className="rounded px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-muted"
                          onClick={() => handleTypeChange(t.value, valeur)}
                        >
                          ½ {libelle}
                        </button>
                      ))}
                    </div>
                  )}
              </div>
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
                  checked={Number(plannedDay.heures_prevues ?? 0) > 0}
                  disabled={plannedDay.type === 'repos'}
                  onCheckedChange={(c) =>
                    updateDayData({
                      jour: dayNumber,
                      heures_prevues: c === true ? 1 : 0,
                    })
                  }
                  className="h-3.5 w-3.5"
                />
                Prévu
              </label>
              <label className="flex items-center gap-2 text-xs">
                <Checkbox
                  checked={Number(actualDay.heures_faites ?? 0) > 0}
                  onCheckedChange={(c) =>
                    updateDayData({
                      jour: dayNumber,
                      heures_faites: c === true ? 1 : 0,
                    })
                  }
                  className="h-3.5 w-3.5"
                />
                Travaillé
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
                  aria-label={`Heures prévues le ${dayNumber}`}
                  disabled={plannedDay.type === 'repos'}
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
                  aria-label={`Heures faites le ${dayNumber}`}
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

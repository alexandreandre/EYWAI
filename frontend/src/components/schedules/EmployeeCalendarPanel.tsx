import { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { CalendarDayCell } from '@/components/CalendarDayCell';
import { CalendarKpiBand } from '@/components/employee-detail/CalendarKpiBand';
import { CalendarAbsencesHint } from '@/components/employee-detail/CalendarAbsencesHint';
import { WeekTemplateForm } from '@/components/schedules/WeekTemplateForm';
import { YearCalendarView } from '@/components/schedules/YearCalendarView';
import { BulkDayActionPanel } from '@/components/schedules/BulkDayActionPanel';
import { useCalendar } from '@/hooks/useCalendar';
import { Loader2, Save, ChevronLeft, ChevronRight, CalendarDays, Grid3x3 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface EmployeeCalendarPanelProps {
  employeeId: string;
  employeeName: string;
  employeeStatut?: string;
  initialYear?: number;
  initialMonth?: number;
  onSaved?: () => void;
}

export function EmployeeCalendarPanel({
  employeeId,
  employeeName,
  employeeStatut,
  initialYear,
  initialMonth,
  onSaved,
}: EmployeeCalendarPanelProps) {
  const [calendarView, setCalendarView] = useState<'month' | 'year'>('month');

  const {
    selectedDate,
    setSelectedDate,
    plannedCalendar,
    actualHours,
    isLoading: isCalendarLoading,
    isSaving,
    saveAllCalendarData,
    updateDayData,
    weekTemplate,
    setWeekTemplate,
    applyWeekTemplate,
    applyWeekTemplateAndSave,
    selectedDays,
    handleDaySelection,
    bulkUpdateDays,
    bulkUpdateDaysAndSave,
    updateSelection,
    isDirty,
    isForfaitJour,
    monthCompletionStatus,
    copyPlannedToActualForDay,
  } = useCalendar(employeeId, employeeStatut);

  useEffect(() => {
    if (initialYear && initialMonth) {
      setSelectedDate({ year: initialYear, month: initialMonth });
    }
  }, [employeeId, initialYear, initialMonth, setSelectedDate]);

  const handlePrevious = () => {
    if (calendarView === 'month') {
      const newMonth = selectedDate.month === 1 ? 12 : selectedDate.month - 1;
      const newYear =
        selectedDate.month === 1 ? selectedDate.year - 1 : selectedDate.year;
      setSelectedDate({ month: newMonth, year: newYear });
    } else {
      setSelectedDate({ month: selectedDate.month, year: selectedDate.year - 1 });
    }
  };

  const handleNext = () => {
    if (calendarView === 'month') {
      const newMonth = selectedDate.month === 12 ? 1 : selectedDate.month + 1;
      const newYear =
        selectedDate.month === 12 ? selectedDate.year + 1 : selectedDate.year;
      setSelectedDate({ month: newMonth, year: newYear });
    } else {
      setSelectedDate({ month: selectedDate.month, year: selectedDate.year + 1 });
    }
  };

  const handleSave = async () => {
    await saveAllCalendarData();
    onSaved?.();
  };

  return (
    <div className="space-y-3 pb-24">
      {isForfaitJour && (
        <div className="rounded-md border border-amber-200/80 bg-amber-50/90 px-3 py-2 text-sm text-amber-950">
          <span className="font-medium">Saisie en jours (forfait jour)</span>
        </div>
      )}

      <Card>
        <CardHeader className="flex flex-row flex-wrap justify-between items-start gap-3 pb-3">
          <div className="flex flex-wrap items-center gap-3">
            <div>
              <CardTitle className="text-lg flex flex-wrap items-center gap-2">
                {employeeName}
                {calendarView === 'month' && (
                  <Badge
                    variant={
                      monthCompletionStatus === 'saisi' ? 'secondary' : 'outline'
                    }
                    className="text-xs font-normal"
                  >
                    {monthCompletionStatus === 'saisi' ? 'Saisi' : 'À saisir'}
                  </Badge>
                )}
              </CardTitle>
              <CardDescription className="flex items-center gap-2 mt-1">
                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handlePrevious}>
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-sm font-medium capitalize min-w-[140px] text-center">
                  {calendarView === 'month'
                    ? new Date(
                        selectedDate.year,
                        selectedDate.month - 1
                      ).toLocaleString('fr-FR', { month: 'long', year: 'numeric' })
                    : selectedDate.year}
                </span>
                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleNext}>
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </CardDescription>
            </div>
            <ToggleGroup
              type="single"
              value={calendarView}
              onValueChange={(v) => v && setCalendarView(v as 'month' | 'year')}
              className="border rounded-lg p-1"
            >
              <ToggleGroupItem value="month" className="gap-1.5 h-8 px-2">
                <CalendarDays className="h-4 w-4" />
                <span className="text-xs">Mois</span>
              </ToggleGroupItem>
              <ToggleGroupItem value="year" className="gap-1.5 h-8 px-2">
                <Grid3x3 className="h-4 w-4" />
                <span className="text-xs">Année</span>
              </ToggleGroupItem>
            </ToggleGroup>
          </div>
          <Button onClick={() => void handleSave()} disabled={isSaving || !isDirty} size="sm">
            {isSaving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            {isSaving ? 'Enregistrement…' : isDirty ? 'Enregistrer' : 'À jour'}
          </Button>
        </CardHeader>

        <CardContent className="p-0 md:p-2">
          {calendarView === 'month' && (
            <>
              <CalendarAbsencesHint
                employeeId={employeeId}
                year={selectedDate.year}
                month={selectedDate.month}
              />
              {!isCalendarLoading && (
                <CalendarKpiBand
                  plannedCalendar={plannedCalendar}
                  actualHours={actualHours}
                  isForfaitJour={isForfaitJour}
                />
              )}
              <WeekTemplateForm
                template={weekTemplate}
                setTemplate={setWeekTemplate}
                onApply={applyWeekTemplate}
                onApplyAndSave={applyWeekTemplateAndSave}
                isSaving={isSaving}
                isForfaitJour={isForfaitJour}
              />
            </>
          )}

          {isCalendarLoading ? (
            <div className="flex h-48 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin" />
            </div>
          ) : calendarView === 'month' ? (
            <div className="flex flex-col gap-3 p-2">
              <div className="grid grid-cols-7 text-center text-xs font-medium text-muted-foreground">
                {['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'].map((d) => (
                  <div key={d}>{d}</div>
                ))}
              </div>
              <div className="grid grid-cols-7 gap-1.5 sm:gap-2">
                {(() => {
                  const year = selectedDate.year;
                  const month = selectedDate.month - 1;
                  const firstDay = new Date(year, month, 1);
                  const lastDay = new Date(year, month + 1, 0);
                  const startDay = (firstDay.getDay() + 6) % 7;
                  const daysInMonth = lastDay.getDate();
                  const cells = [];
                  for (let i = 0; i < startDay; i++) {
                    cells.push(<div key={`empty-${i}`} />);
                  }
                  for (let day = 1; day <= daysInMonth; day++) {
                    const date = new Date(year, month, day);
                    const isToday =
                      date.toDateString() === new Date().toDateString();
                    const arg = {
                      date,
                      dayNumberText: String(day),
                      isToday,
                    } as Parameters<typeof CalendarDayCell>[0]['arg'];
                    cells.push(
                      <div
                        key={day}
                        className="min-h-[7.5rem] rounded-xl bg-card shadow-sm"
                      >
                        <CalendarDayCell
                          arg={arg}
                          plannedCalendar={plannedCalendar}
                          actualHours={actualHours}
                          updateDayData={updateDayData}
                          selectedDays={selectedDays}
                          onDaySelect={handleDaySelection}
                          selectedDate={selectedDate}
                          isForfaitJour={isForfaitJour}
                          onCopyPlannedToActual={copyPlannedToActualForDay}
                        />
                      </div>
                    );
                  }
                  return cells;
                })()}
              </div>
            </div>
          ) : (
            <YearCalendarView
              year={selectedDate.year}
              employeeId={employeeId}
              isForfaitJour={isForfaitJour}
              onMonthClick={(month) => {
                setSelectedDate({ year: selectedDate.year, month });
                setCalendarView('month');
              }}
            />
          )}
        </CardContent>
      </Card>

      {selectedDays.length > 0 && (
        <BulkDayActionPanel
          selectedCount={selectedDays.length}
          onBulkUpdate={bulkUpdateDays}
          updateSelection={updateSelection}
          onBulkUpdateAndSave={bulkUpdateDaysAndSave}
          isSaving={isSaving}
          isForfaitJour={isForfaitJour}
        />
      )}
    </div>
  );
}

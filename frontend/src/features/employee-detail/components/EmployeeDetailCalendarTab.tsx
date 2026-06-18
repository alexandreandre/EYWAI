import { useMemo, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, Grid3x3, Loader2, Save, Sparkles, Upload } from "lucide-react";
import { CalendarDayCell } from "@/components/CalendarDayCell";
import { CalendarAbsencesHint } from "@/components/employee-detail/CalendarAbsencesHint";
import { CalendarKpiBand } from "@/components/employee-detail/CalendarKpiBand";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { BulkActionPanel } from "@/features/employee-detail/components/calendar/BulkActionPanel";
import { WeekTemplateForm } from "@/features/employee-detail/components/calendar/WeekTemplateForm";
import { YearCalendarView } from "@/features/employee-detail/components/calendar/YearCalendarView";
import { AssistedFillDialog } from "@/components/schedules/assisted-fill/AssistedFillDialog";
import { PointageImportDialog } from "@/components/schedules/assisted-fill/PointageImportDialog";
import type { Employee } from "@/features/employee-detail/types";
import { WeekTemplate } from "@/hooks/useCalendar";
import type { DayData } from "@/components/ScheduleModal";

interface CalendarTabProps {
  employee: Employee;
  employeeId: string;
  activeCompanyId: string;
  isForfaitJour: boolean;
  calendarView: "month" | "year";
  setCalendarView: (v: "month" | "year") => void;
  selectedDate: { year: number; month: number };
  setSelectedDate: (d: { year: number; month: number }) => void;
  plannedCalendar: DayData[];
  actualHours: DayData[];
  isCalendarLoading: boolean;
  isSaving: boolean;
  saveAllCalendarData: () => void;
  updateDayData: (day: number, data: Partial<Omit<DayData, "jour">>) => void;
  weekTemplate: WeekTemplate;
  setWeekTemplate: React.Dispatch<React.SetStateAction<WeekTemplate>>;
  applyWeekTemplate: () => void;
  applyWeekTemplateAndSave: () => void;
  selectedDays: number[];
  handleDaySelection: (day: number, multi: boolean) => void;
  bulkUpdateDays: (data: Partial<Omit<DayData, "jour">>) => void;
  bulkUpdateDaysAndSave: (data: Partial<Omit<DayData, "jour">>) => void;
  updateSelection: (mode: "all" | "weekdays" | "none") => void;
  isDirty: boolean;
  monthCompletionStatus: string;
  copyPreviousMonthPlanned: () => void | Promise<void>;
  copyPlannedToActualForDay: (day: number) => void;
  bulkCopyPlannedToActual: () => void;
  isCopyingPrevMonth: boolean;
  reloadCalendar: () => void;
}

export function EmployeeDetailCalendarTab(props: CalendarTabProps) {
  const {
    employee,
    employeeId,
    activeCompanyId,
    isForfaitJour,
    calendarView,
    setCalendarView,
    selectedDate,
    setSelectedDate,
    plannedCalendar,
    actualHours,
    isCalendarLoading,
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
    monthCompletionStatus,
    copyPreviousMonthPlanned,
    copyPlannedToActualForDay,
    bulkCopyPlannedToActual,
    isCopyingPrevMonth,
    reloadCalendar,
  } = props;

  const [assistedFillOpen, setAssistedFillOpen] = useState(false);
  const [pointageImportOpen, setPointageImportOpen] = useState(false);

  const roster = useMemo(
    () => [
      {
        id: employeeId,
        first_name: employee.first_name,
        last_name: employee.last_name,
      },
    ],
    [employeeId, employee.first_name, employee.last_name],
  );

  return (
    <>
          {isForfaitJour && employee && (
            <div className="mb-2 rounded-md border border-amber-200/80 bg-amber-50/90 px-3 py-2 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100">
              <span className="font-medium">Saisie en jours (forfait jour)</span>
              {employee.statut ? (
                <span className="text-muted-foreground"> — statut : {employee.statut}</span>
              ) : null}
            </div>
          )}
          {!isForfaitJour && (
            <div className="mb-2 rounded-md border bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground">
              Saisie en heures
            </div>
          )}
          <Card className="mt-3">
             <CardHeader className="flex flex-row justify-between items-center">
                <div className="flex items-center gap-4">
                  <div>
                    <CardTitle className="text-xl font-semibold text-foreground flex flex-wrap items-center gap-2">
                      Calendrier de {employee.first_name} {employee.last_name}
                      {calendarView === 'month' && (
                        <Badge
                          variant={monthCompletionStatus === 'saisi' ? 'secondary' : 'outline'}
                          className="text-xs font-normal"
                        >
                          {monthCompletionStatus === 'saisi' ? 'Saisi' : 'À saisir'}
                        </Badge>
                      )}
                    </CardTitle>

                    <CardDescription className="flex items-center gap-3 mt-0">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-gray-600 hover:text-primary transition"
                        onClick={() => {
                          if (calendarView === 'month') {
                            const newMonth = selectedDate.month === 1 ? 12 : selectedDate.month - 1;
                            const newYear = selectedDate.month === 1 ? selectedDate.year - 1 : selectedDate.year;
                            setSelectedDate({ month: newMonth, year: newYear });
                          } else {
                            setSelectedDate({ month: selectedDate.month, year: selectedDate.year - 1 });
                          }
                        }}
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </Button>

                      <span className="text-base font-medium capitalize text-foreground/90 tracking-wide">
                        {calendarView === 'month'
                          ? new Date(selectedDate.year, selectedDate.month - 1).toLocaleString("fr-FR", {
                              month: "long",
                              year: "numeric",
                            })
                          : selectedDate.year
                        }
                      </span>

                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-gray-600 hover:text-primary transition"
                        onClick={() => {
                          if (calendarView === 'month') {
                            const newMonth = selectedDate.month === 12 ? 1 : selectedDate.month + 1;
                            const newYear = selectedDate.month === 12 ? selectedDate.year + 1 : selectedDate.year;
                            setSelectedDate({ month: newMonth, year: newYear });
                          } else {
                            setSelectedDate({ month: selectedDate.month, year: selectedDate.year + 1 });
                          }
                        }}
                      >
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </CardDescription>

                  </div>

                  {/* ✅ NOUVEAU : Toggle pour basculer entre vue mensuelle et annuelle (calendrier) */}
                  <ToggleGroup
                    type="single"
                    value={calendarView}
                    onValueChange={(value) => value && setCalendarView(value as 'month' | 'year')}
                    className="border rounded-lg p-1"
                  >
                    <ToggleGroupItem value="month" aria-label="Vue mensuelle" className="gap-2">
                      <CalendarDays className="h-4 w-4" />
                      <span className="hidden sm:inline">Mois</span>
                    </ToggleGroupItem>
                    <ToggleGroupItem value="year" aria-label="Vue annuelle (calendrier)" className="gap-2">
                      <Grid3x3 className="h-4 w-4" />
                      <span className="hidden sm:inline">Année</span>
                    </ToggleGroupItem>
                  </ToggleGroup>
                </div>

                {/* ✅ MODIFIÉ : Le bouton principal, avec la parenthèse manquante corrigée */}
                <div className="flex flex-wrap items-center gap-2">
                  {!isDirty && !isSaving && (
                    <Badge variant="outline" className="text-xs font-normal text-muted-foreground">
                      À jour
                    </Badge>
                  )}
                  <Button
                    variant="outline"
                    onClick={() => setAssistedFillOpen(true)}
                    title="Remplir le calendrier de ce collaborateur par IA (texte ou dictée)"
                  >
                    <Sparkles className="mr-2 h-4 w-4" />
                    <span className="hidden sm:inline">Remplir par IA</span>
                    <span className="sm:hidden">IA</span>
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => setPointageImportOpen(true)}
                    title="Importer un relevé de pointeuse pour ce collaborateur"
                  >
                    <Upload className="mr-2 h-4 w-4" />
                    <span className="hidden sm:inline">Importer un relevé</span>
                    <span className="sm:hidden">Import</span>
                  </Button>
                  <Button
                    onClick={saveAllCalendarData}
                    disabled={isSaving || !isDirty}
                  >
                    {isSaving ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="mr-2 h-4 w-4" />
                    )}
                    {isSaving ? "Enregistrement..." : "Enregistrer"}
                  </Button>
                </div>
             </CardHeader>
             {calendarView === 'month' && (
               <CardDescription className="mt-1 ml-6 text-sm text-muted-foreground">
                  Cliquez sur un jour pour éditer le planning et les heures réalisées.
                </CardDescription>
             )}


             <CardContent className="p-0 md:p-2 pb-48">
                {calendarView === 'month' && employeeId && (
                  <CalendarAbsencesHint
                    employeeId={employeeId}
                    year={selectedDate.year}
                    month={selectedDate.month}
                  />
                )}
                {calendarView === 'month' && !isCalendarLoading && (
                  <CalendarKpiBand
                    plannedCalendar={plannedCalendar}
                    actualHours={actualHours}
                    isForfaitJour={isForfaitJour}
                  />
                )}
                {calendarView === 'month' && (
                  <WeekTemplateForm
                    template={weekTemplate}
                    setTemplate={setWeekTemplate}
                    onApply={applyWeekTemplate}
                    onApplyAndSave={applyWeekTemplateAndSave}
                    onCopyPreviousMonth={() => void copyPreviousMonthPlanned()}
                    isSaving={isSaving}
                    isCopyingPrevMonth={isCopyingPrevMonth}
                    isForfaitJour={isForfaitJour}
                    companyId={activeCompanyId}
                    daysInMonth={new Date(selectedDate.year, selectedDate.month, 0).getDate()}
                  />
                )}
                {isCalendarLoading ? <div className="flex h-full items-center justify-center"><Loader2 className="h-8 w-8 animate-spin" /></div> : (
                  <>
                    {calendarView === 'month' ? (
                      <div className="flex flex-col gap-4 p-2">
                    {/* Noms des jours */}
                    <div className="grid grid-cols-7 text-center text-sm font-medium text-muted-foreground">
                      {["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"].map((d) => (
                        <div key={d}>{d}</div>
                      ))}
                    </div>

                    {/* Cases des jours */}
                    <div className="grid grid-cols-7 gap-2 sm:gap-3">
                      {(() => {
                        const year = selectedDate.year;
                        const month = selectedDate.month - 1;
                        const firstDay = new Date(year, month, 1);
                        const lastDay = new Date(year, month + 1, 0);
                        const startDay = (firstDay.getDay() + 6) % 7;
                        const daysInMonth = lastDay.getDate();

                        const days = [];
                        for (let i = 0; i < startDay; i++) days.push(<div key={`empty-${i}`} />);
                        for (let day = 1; day <= daysInMonth; day++) {
                          const date = new Date(year, month, day);
                          const isToday = date.toDateString() === new Date().toDateString();
                          const arg = { date, dayNumberText: String(day), isToday } as any;

                          days.push(
                            <div
                              key={day}
                              className="min-h-[8.5rem] rounded-2xl bg-white dark:bg-slate-900/40 shadow-sm hover:shadow-md transition-all"
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
                        return days;
                      })()}
                    </div>
                      </div>
                    ) : (
                      <YearCalendarView
                        year={selectedDate.year}
                        employeeId={employeeId!}
                        isForfaitJour={isForfaitJour}
                        onMonthClick={(month) => {
                          setSelectedDate({ year: selectedDate.year, month });
                          setCalendarView('month');
                        }}
                      />
                    )}
                  </>
                )}
             </CardContent>
           </Card>

      {selectedDays.length > 0 && (
        <BulkActionPanel
          selectedCount={selectedDays.length}
          onBulkUpdate={bulkUpdateDays}
          updateSelection={updateSelection}
          onBulkUpdateAndSave={bulkUpdateDaysAndSave}
          onBulkCopyPlannedToActual={bulkCopyPlannedToActual}
          isSaving={isSaving}
          isForfaitJour={isForfaitJour}
        />
      )}

      <AssistedFillDialog
        open={assistedFillOpen}
        onOpenChange={setAssistedFillOpen}
        year={selectedDate.year}
        month={selectedDate.month}
        roster={roster}
        singleEmployee
        onApplied={reloadCalendar}
      />

      <PointageImportDialog
        open={pointageImportOpen}
        onOpenChange={setPointageImportOpen}
        year={selectedDate.year}
        month={selectedDate.month}
        roster={roster}
        singleEmployee
        onApplied={reloadCalendar}
        onNavigateToMonth={(y, m) => setSelectedDate({ year: y, month: m })}
      />
    </>
  );
}

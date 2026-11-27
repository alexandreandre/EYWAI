import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPeriodeVariables } from '@/api/periodeVariables';
import { bornesDuSalarie } from '@/lib/schedulesOverview';
import { computeMonthCompletionStatus, joursASaisir } from '@/lib/calendarStats';
import { alerteDeSaisie } from '@/lib/alerteDeSaisie';
import { pastilleSaisieDuMois } from '@/lib/calendrierPilotage';
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
import { CalendarEntryHelp } from '@/components/schedules/CalendarEntryHelp';
import { WeekTemplateForm } from '@/components/schedules/WeekTemplateForm';
import { YearCalendarView } from '@/components/schedules/YearCalendarView';
import { BulkDayActionPanel } from '@/components/schedules/BulkDayActionPanel';
import { useCalendar } from '@/hooks/useCalendar';
import { CalendarSyncNotice } from '@/components/schedules/CalendarSyncNotice';
import { Loader2, Save, ChevronLeft, ChevronRight, CalendarDays, Grid3x3, Trash2 } from 'lucide-react';
import { ViderCalendrierDialog } from '@/components/schedules/ViderCalendrierDialog';
import { AbsenceRequestModal } from '@/components/AbsenceRequestModal';
import { useBasculeDeLaSociete } from '@/hooks/useBasculeDeLaSociete';
import { Chargement } from '@/components/Chargement';
import { cn } from '@/lib/utils';
import { useCasesVoisines } from '@/components/schedules/useCasesVoisines';

interface EmployeeCalendarPanelProps {
  employeeId: string;
  employeeName: string;
  employeeStatut?: string;
  employeeIsForfaitJour?: boolean | null;
  /** Sortie du salarié : après, les cases sont grisées et rien n'est attendu. */
  employeeSortie?: { exit_last_working_day?: string | null; hire_date?: string | null };
  initialYear?: number;
  initialMonth?: number;
  onSaved?: () => void;
  /** Début de la première paie Martine (bascule) : avant, rien n'est compté. */
  debutMartine?: string | null;
}

export function EmployeeCalendarPanel({
  employeeId,
  employeeName,
  employeeStatut,
  employeeIsForfaitJour,
  employeeSortie,
  initialYear,
  initialMonth,
  onSaved,
  debutMartine = null,
}: EmployeeCalendarPanelProps) {
  const [calendarView, setCalendarView] = useState<'month' | 'year'>('month');
  const [viderOuvert, setViderOuvert] = useState(false);
  // Le tiroir change de mois : la bascule de la société vaut pour tous.
  const basculeSociete = useBasculeDeLaSociete();
  const debutPaieMartine = debutMartine ?? basculeSociete?.debutMartine ?? null;
  const [debutArret, setDebutArret] = useState<Date | null>(null);

  const {
    selectedDate,
    setSelectedDate,
    plannedCalendar,
    actualHours,
    joursEnConflit,
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
    pointe,
    copyPlannedToActualForDay,
    loadError,
    saveError,
    refetch,
  } = useCalendar(employeeId, employeeStatut, {
    isForfaitJour: employeeIsForfaitJour,
    sortie: employeeSortie ?? null,
  });

  // Même jugement que la liste : jusqu'à l'arrêté des variables (les jours
  // d'après sont au mois suivant) et jusqu'à la sortie (retour du 10/11).
  const fenetreQuery = useQuery({
    queryKey: ['periode-variables', selectedDate.year, selectedDate.month],
    queryFn: () => getPeriodeVariables(selectedDate.year, selectedDate.month),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const { bornes, dernierJourContrat, premierJourContrat, premierJourMartine } = bornesDuSalarie(
    {
      id: employeeId,
      first_name: '',
      last_name: '',
      exit_last_working_day: employeeSortie?.exit_last_working_day ?? null,
      hire_date: employeeSortie?.hire_date ?? null,
    },
    selectedDate.year,
    selectedDate.month,
    isForfaitJour,
    { finFenetre: fenetreQuery.data?.fin ?? null, debutMartine: debutPaieMartine }
  );
  const statutBorne =
    monthCompletionStatus === 'saisi'
      ? 'saisi'
      : computeMonthCompletionStatus(
          plannedCalendar,
          actualHours,
          selectedDate.year,
          selectedDate.month,
          isForfaitJour,
          pointe,
          bornes
        );
  const alerte = isCalendarLoading
    ? null
    : alerteDeSaisie(
        {
          rowStatus: statutBorne,
          joursASaisir: joursASaisir(
            plannedCalendar,
            actualHours,
            selectedDate.year,
            selectedDate.month,
            isForfaitJour,
            pointe,
            bornes
          ),
          dernierJourJuge: bornes.dernierJour ?? null,
          dernierJourContrat,
          premierJourContrat,
          premierJourMartine,
          debutMartine: debutPaieMartine,
          logicielPrecedent: basculeSociete?.logiciel ?? null,
        },
        selectedDate.year,
        selectedDate.month
      );

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

  const casesVoisines = useCasesVoisines({
    employeeId,
    annee: selectedDate.year,
    mois: selectedDate.month,
    actif: calendarView === 'month',
    isForfaitJour,
    isDirty,
    ouvrirMois: setSelectedDate,
  });

  const handleSave = async () => {
    if (await saveAllCalendarData()) onSaved?.();
  };

  return (
    <div className="space-y-3 pb-24">
      <CalendarSyncNotice loadError={loadError} saveError={saveError} isDirty={isDirty} onReload={() => void refetch()} />
      {isForfaitJour && (
        <div className="rounded-md border border-amber-200/80 bg-amber-50/90 px-3 py-2 text-sm text-amber-950">
          <span className="font-medium">Cadre forfait jours</span>
          <span className="text-amber-900/75"> — calendrier sans horaires</span>
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
                      pastilleSaisieDuMois(statutBorne, joursEnConflit) === 'Saisi'
                        ? 'secondary'
                        : 'outline'
                    }
                    className="text-xs font-normal"
                  >
                    {pastilleSaisieDuMois(statutBorne, joursEnConflit)}
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
          <div className="flex flex-wrap items-center gap-2">
          {calendarView === 'month' && (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setViderOuvert(true)}
              disabled={isSaving || isDirty || isCalendarLoading || loadError}
              title={
                isDirty
                  ? 'Enregistrez ou annulez d’abord vos changements'
                  : 'Annule un modèle appliqué par erreur : prévu et réel du mois remis à vide, sauf arrêts, congés, absences et jours d’un bulletin validé'
              }
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Vider le calendrier du mois
            </Button>
          )}
          <Button onClick={() => void handleSave()} disabled={isSaving || !isDirty} size="sm">
            {isSaving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            {isSaving ? 'Enregistrement…' : isDirty ? 'Enregistrer' : 'À jour'}
          </Button>
          </div>
        </CardHeader>

        <CardContent className="p-0 md:p-2">
          {calendarView === 'month' && (
            <>
              {alerte && (
                <p
                  className="mx-2 mb-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive"
                  data-testid="alerte-jours-a-saisir-tiroir"
                >
                  {alerte.detail}
                </p>
              )}
              {!isForfaitJour && <CalendarEntryHelp />}
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

          {loadError ? null : isCalendarLoading ? (
            <Chargement label="Chargement du calendrier…" className="h-48" />
          ) : calendarView === 'month' ? (
            <div className="flex flex-col gap-3 p-2">
              <div className="sticky top-[var(--entete-tiroir,0px)] z-20 -mx-2 grid grid-cols-7 bg-background/95 px-2 py-1.5 text-center backdrop-blur border-b text-xs font-medium text-muted-foreground" data-testid="entete-jours-du-mois">
                {['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'].map((d) => (
                  <div key={d}>{d}</div>
                ))}
              </div>
              <div className="grid grid-cols-7 gap-1.5 sm:gap-2">
                {(() => {
                  const year = selectedDate.year;
                  const month = selectedDate.month - 1;
                  const lastDay = new Date(year, month + 1, 0);
                  const daysInMonth = lastDay.getDate();
                  const cells = [];
                  cells.push(...casesVoisines.avant);
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
                          joursEnConflit={joursEnConflit}
                          updateDayData={updateDayData}
                          selectedDays={selectedDays}
                          onDaySelect={handleDaySelection}
                          selectedDate={selectedDate}
                          isForfaitJour={isForfaitJour}
                          pointe={pointe}
                          onCopyPlannedToActual={copyPlannedToActualForDay}
                          dernierJourJuge={bornes.dernierJour ?? null}
                          dernierJourContrat={dernierJourContrat}
                          premierJourJuge={bornes.premierJour ?? null}
                          premierJourContrat={premierJourContrat}
                          onSignalerArret={(jour) =>
                            setDebutArret(new Date(selectedDate.year, selectedDate.month - 1, jour))
                          }
                          signalerArretIndisponible={isDirty ? 'Enregistrez d’abord le calendrier : la saisie de l’arrêt le recharge.' : null}
                        />
                      </div>
                    );
                  }
                  cells.push(...casesVoisines.apres);
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

      <AbsenceRequestModal
        isOpen={debutArret !== null}
        onClose={() => setDebutArret(null)}
        onSuccess={() => {
          setDebutArret(null);
          void refetch();
          onSaved?.();
        }}
        mode="rh_arret"
        salarieInitial={employeeId}
        typeInitial="arret_maladie"
        debutArretInitial={debutArret ?? undefined}
      />

      <ViderCalendrierDialog
        open={viderOuvert}
        onOpenChange={setViderOuvert}
        salaries={[{ id: employeeId, nom: employeeName }]}
        year={selectedDate.year}
        month={selectedDate.month}
        onDone={() => {
          void refetch();
          onSaved?.();
        }}
      />

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

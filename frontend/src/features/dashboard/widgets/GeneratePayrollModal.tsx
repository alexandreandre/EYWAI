import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { AlertTriangle, Loader2, PartyPopper } from 'lucide-react';
import { PayrollProgressBar } from '@/features/payroll/components/PayrollProgressBar';
import { PayrollPreflightChecklist } from '@/features/payroll/components/PayrollPreflightChecklist';
import { PayrollPreflightAcknowledgeDialog } from '@/features/payroll/components/review/PayrollPreflightAcknowledgeDialog';
import { usePayrollGeneration } from '@/features/payroll/hooks/usePayrollGeneration';
import { usePreflightAnomaliesCount } from '@/features/payroll/hooks/usePreflightAnomaliesCount';
import { PayrollEmployeeEmptyState } from '@/features/payroll/components/PayrollEmployeeEmptyState';
import { PayrollEmployeeReadinessAlert } from '@/features/payroll/components/PayrollEmployeeReadinessAlert';
import { acknowledgePreflight } from '@/api/payrollPreflight';
import type { PayrollGenerateEmployee } from '@/features/payroll/types';
import type { EmployeeListItem } from '@/hooks/queries/useEmployeesQuery';

export type { PayrollGenerateEmployee } from '@/features/payroll/types';

interface GeneratePayrollModalProps {
  isOpen: boolean;
  onClose: () => void;
  employees: PayrollGenerateEmployee[];
  allEmployees?: EmployeeListItem[];
  employeesLoading?: boolean;
  employeesError?: string | null;
  onRetryEmployees?: () => void;
  onNavigateTo?: (path: string) => void;
}

type Phase = 'select' | 'running' | 'done';

export function GeneratePayrollModal({
  isOpen,
  onClose,
  employees,
  allEmployees = [],
  employeesLoading = false,
  employeesError = null,
  onRetryEmployees,
  onNavigateTo,
}: GeneratePayrollModalProps) {
  const [selectedEmployees, setSelectedEmployees] = useState<Set<string>>(new Set());
  const [selectedMonth, setSelectedMonth] = useState<string>('');
  const [uiPhase, setUiPhase] = useState<Phase>('select');
  const [ackOpen, setAckOpen] = useState(false);
  const [ackConfirmed, setAckConfirmed] = useState(false);
  const [ackSubmitting, setAckSubmitting] = useState(false);
  const feedRef = useRef<HTMLDivElement>(null);

  const generation = usePayrollGeneration();

  const parsedMonth = selectedMonth
    ? {
        year: parseInt(selectedMonth.split('-')[0], 10),
        month: parseInt(selectedMonth.split('-')[1], 10),
      }
    : { year: 0, month: 0 };

  const {
    data: preflightData,
    openAnomaliesCount,
    isLoading: preflightLoading,
  } = usePreflightAnomaliesCount(parsedMonth.year, parsedMonth.month, !!selectedMonth);

  const generateMonthOptions = () => {
    const options = [];
    const now = new Date();

    for (let i = -12; i <= 2; i++) {
      const date = new Date(now.getFullYear(), now.getMonth() + i, 1);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const value = `${year}-${month}`;
      const label = date.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
      options.push({ value, label: label.charAt(0).toUpperCase() + label.slice(1) });
    }

    return options;
  };

  const monthOptions = generateMonthOptions();

  const selectedMonthLabel =
    monthOptions.find((o) => o.value === selectedMonth)?.label ?? '';

  useEffect(() => {
    const now = new Date();
    const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    setSelectedMonth(currentMonth);
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    setUiPhase('select');
    setSelectedEmployees(new Set());
    generation.reset();
  }, [isOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (generation.phase === 'running') {
      setUiPhase('running');
    } else if (generation.phase === 'done') {
      setUiPhase('done');
    }
  }, [generation.phase]);

  useEffect(() => {
    if (!isOpen || uiPhase !== 'done' || generation.phase !== 'done') return;

    const hasErrors = generation.log.some((e) => e.status === 'error');
    const hasWarnings = generation.log.some((e) => e.status === 'warning');
    if (hasErrors || hasWarnings) return;

    const delayMs = generation.totalJobs <= 1 ? 3500 : 6000;
    const timer = window.setTimeout(() => {
      handleClose();
    }, delayMs);

    return () => window.clearTimeout(timer);
  }, [isOpen, uiPhase, generation.phase, generation.log, generation.totalJobs]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [generation.log, generation.currentLabel]);

  useEffect(() => () => generation.dismiss(), []); // eslint-disable-line react-hooks/exhaustive-deps

  const eligibleEmployees = employees.filter((e) => e.payroll_eligible !== false);
  const ineligibleCount = employees.length - eligibleEmployees.length;
  const selectableEmployees =
    ineligibleCount > 0 ? eligibleEmployees : employees;

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedEmployees(new Set(eligibleEmployees.map((e) => e.id)));
    } else {
      setSelectedEmployees(new Set());
    }
  };

  const handleSelect = (id: string, checked: boolean) => {
    const employee = employees.find((e) => e.id === id);
    if (!employee || employee.payroll_eligible === false) return;
    const newSet = new Set(selectedEmployees);
    if (checked) {
      newSet.add(id);
    } else {
      newSet.delete(id);
    }
    setSelectedEmployees(newSet);
  };

  const handleGenerate = () => {
    if (openAnomaliesCount > 0) {
      setAckConfirmed(false);
      setAckOpen(true);
      return;
    }
    startGeneration();
  };

  const startGeneration = () => {
    const ids = Array.from(selectedEmployees);
    const [yearStr, monthStr] = selectedMonth.split('-');
    const year = parseInt(yearStr, 10);
    const month = parseInt(monthStr, 10);

    const jobs = ids.map((employeeId) => {
      const employee = employees.find((e) => e.id === employeeId);
      const employeeName = employee
        ? `${employee.first_name} ${employee.last_name}`
        : employeeId;
      return { employeeId, employeeName, year, month };
    });

    setUiPhase('running');
    generation.generateJobs(jobs);
  };

  const handleAcknowledgeAndGenerate = async () => {
    if (!selectedMonth || !preflightData) return;
    setAckSubmitting(true);
    try {
      const summary = [
        ...(preflightData.counts.ecart_heures > 0 ? ['ecart_heures'] : []),
        ...(preflightData.counts.heures_non_saisies > 0 ? ['heures_non_saisies'] : []),
        ...(preflightData.counts.pointage > 0 ? ['pointage'] : []),
        ...(preflightData.counts.conflit_absence > 0 ? ['conflit_absence'] : []),
      ];
      await acknowledgePreflight({
        year: parsedMonth.year,
        month: parsedMonth.month,
        open_anomalies_count: openAnomaliesCount,
        anomaly_types_summary: summary,
      });
      setAckOpen(false);
      startGeneration();
    } finally {
      setAckSubmitting(false);
    }
  };

  const handleReset = () => {
    generation.reset();
    setUiPhase('select');
  };

  const handleClose = () => {
    generation.dismiss();
    onClose();
  };

  const isAllSelected =
    eligibleEmployees.length > 0 &&
    selectedEmployees.size === eligibleEmployees.length;
  const successCount = generation.log.filter((l) => l.status === 'success').length;
  const warningCount = generation.log.filter((l) => l.status === 'warning').length;
  const generatedCount = successCount + warningCount;
  const errorCount = generation.log.filter((l) => l.status === 'error').length;

  return (
    <>
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open && uiPhase !== 'running') handleClose();
      }}
    >
      <DialogContent className="max-w-md p-0 max-h-[90vh] overflow-y-auto" hideClose={uiPhase === 'running'}>
        <DialogHeader className="p-6 pb-4">
          <DialogTitle>
            {uiPhase === 'select' && 'Générer la Paie'}
            {uiPhase === 'running' && 'Génération en cours…'}
            {uiPhase === 'done' && 'Génération terminée'}
          </DialogTitle>
        </DialogHeader>

        {uiPhase === 'select' && (
          <>
            <div className="px-6 pb-4">
              <PayrollPreflightChecklist onStepClick={onNavigateTo} payrollMonth={selectedMonth} />
            </div>

            {openAnomaliesCount > 0 && !preflightLoading && (
              <div className="mx-6 mb-4 rounded-lg border border-amber-300/60 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/20 dark:text-amber-100">
                {openAnomaliesCount} anomalie{openAnomaliesCount > 1 ? 's' : ''} ouverte
                {openAnomaliesCount > 1 ? 's' : ''} pour ce mois — un acquittement sera demandé avant
                la génération.
              </div>
            )}

            <div className="px-6 pb-4">
              <Label htmlFor="month-select" className="text-sm font-medium mb-2 block">
                Mois de paie
              </Label>
              <Select value={selectedMonth} onValueChange={setSelectedMonth}>
                <SelectTrigger id="month-select">
                  <SelectValue placeholder="Sélectionner un mois" />
                </SelectTrigger>
                <SelectContent>
                  {monthOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {employees.length > 0 && (
              <div className="px-6 pb-4">
                <PayrollEmployeeReadinessAlert
                  employees={employees}
                  onNavigateTo={onNavigateTo}
                />
              </div>
            )}

            {employees.length === 0 ? (
              <div className="px-6 pb-4">
                <PayrollEmployeeEmptyState
                  loading={employeesLoading}
                  errorMessage={employeesError}
                  onRetry={onRetryEmployees}
                  allEmployees={allEmployees}
                  onNavigateTo={onNavigateTo}
                />
              </div>
            ) : eligibleEmployees.length === 0 ? null : (
              <div className="px-2 pb-2">
                {ineligibleCount > 0 && (
                  <p className="px-4 pb-2 text-xs text-muted-foreground">
                    {eligibleEmployees.length} collaborateur{eligibleEmployees.length > 1 ? 's' : ''}{' '}
                    prêt{eligibleEmployees.length > 1 ? 's' : ''} — les autres sont listés dans le
                    détail ci-dessus.
                  </p>
                )}
                <Command className="rounded-lg border border-border/60">
                  <CommandInput placeholder="Rechercher un employé..." className="h-10" />
                  <CommandList className="max-h-[240px] overflow-y-auto">
                    <CommandEmpty>Aucun employé trouvé.</CommandEmpty>
                    <CommandGroup>
                      <CommandItem
                        onSelect={() => handleSelectAll(!isAllSelected)}
                        className="flex items-center gap-3"
                      >
                        <Checkbox checked={isAllSelected} onCheckedChange={handleSelectAll} />
                        <span className="text-sm font-medium">Tout sélectionner</span>
                      </CommandItem>
                      {selectableEmployees.map((emp) => (
                        <CommandItem
                          key={emp.id}
                          value={`${emp.first_name} ${emp.last_name}`}
                          onSelect={() =>
                            handleSelect(emp.id, !selectedEmployees.has(emp.id))
                          }
                          className="flex items-center gap-3"
                        >
                          <Checkbox
                            checked={selectedEmployees.has(emp.id)}
                            onCheckedChange={(checked) => handleSelect(emp.id, !!checked)}
                          />
                          <span className="text-sm">
                            {emp.first_name} {emp.last_name}
                          </span>
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </div>
            )}

            <div className="space-y-2 p-6 pt-2">
              {employees.length === 0 && !employeesLoading && !employeesError && (
                <p className="text-center text-xs text-muted-foreground">
                  Le bouton Générer sera disponible dès qu&apos;au moins un collaborateur actif
                  aura une fiche paie complète.
                </p>
              )}
              {eligibleEmployees.length === 0 && employees.length > 0 && (
                <p className="text-center text-xs text-muted-foreground">
                  Le bouton Générer sera disponible une fois au moins une fiche complète.
                </p>
              )}
              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={handleClose}>
                  Annuler
                </Button>
                <Button
                  className="bg-cyan-500 hover:bg-cyan-600 text-white"
                  onClick={handleGenerate}
                  disabled={selectedEmployees.size === 0 || !selectedMonth}
                  title={
                    selectedEmployees.size === 0 && employees.length > 0
                      ? 'Sélectionnez au moins un collaborateur dont la fiche paie est complète'
                      : undefined
                  }
                >
                  Générer ({selectedEmployees.size})
                </Button>
              </div>
            </div>
          </>
        )}

        {(uiPhase === 'running' || uiPhase === 'done') && (
          <div className="px-6 pb-2">
            {selectedMonthLabel && (
              <p className="mb-3 text-xs text-muted-foreground">{selectedMonthLabel}</p>
            )}

            {generation.phase !== 'idle' && (
              <div ref={feedRef}>
                <PayrollProgressBar
                  phase={generation.phase}
                  progress={generation.progress}
                  currentLabel={generation.currentLabel}
                  estimatedRemainingSec={generation.estimatedRemainingSec}
                  log={generation.log}
                  totalJobs={generation.totalJobs}
                  completedCount={generation.completedCount}
                  onDismiss={generation.dismiss}
                  onCancel={generation.cancel}
                />
              </div>
            )}

            {uiPhase === 'done' && (
              <div className="mt-4 flex items-center gap-2 rounded-lg bg-muted/40 p-3 text-sm">
                {errorCount > 0 ? (
                  <span className="text-foreground">
                    <span className="font-medium text-green-700">
                      {generatedCount} généré{generatedCount !== 1 ? 's' : ''}
                    </span>
                    {' · '}
                    <span className="font-medium text-red-600">
                      {errorCount} en échec
                    </span>
                  </span>
                ) : generatedCount === 0 ? (
                  <span className="text-muted-foreground">Aucun bulletin généré.</span>
                ) : warningCount === 0 ? (
                  <>
                    <PartyPopper className="h-5 w-5 shrink-0 text-green-600" />
                    <span className="font-medium text-green-700">
                      {generatedCount} bulletin{generatedCount > 1 ? 's' : ''} généré
                      {generatedCount > 1 ? 's' : ''} avec succès.
                    </span>
                  </>
                ) : successCount === 0 ? (
                  <>
                    <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600" />
                    <span className="font-medium text-amber-700">
                      {generatedCount} bulletin{generatedCount > 1 ? 's' : ''} généré
                      {generatedCount > 1 ? 's' : ''} avec des alertes.
                    </span>
                  </>
                ) : (
                  <>
                    <PartyPopper className="h-5 w-5 shrink-0 text-green-600" />
                    <span className="text-foreground">
                      <span className="font-medium text-green-700">
                        {successCount} sans alerte
                      </span>
                      {' · '}
                      <span className="font-medium text-amber-700">
                        {warningCount} avec alerte{warningCount > 1 ? 's' : ''}
                      </span>
                    </span>
                  </>
                )}
              </div>
            )}

            <div className="p-6 pt-4 flex justify-end gap-2">
              {uiPhase === 'running' ? (
                <Button variant="ghost" disabled>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Génération…
                </Button>
              ) : (
                <>
                  {errorCount > 0 && (
                    <Button variant="ghost" onClick={handleReset}>
                      Nouvelle sélection
                    </Button>
                  )}
                  <Button
                    className="bg-cyan-500 hover:bg-cyan-600 text-white"
                    onClick={handleClose}
                  >
                    Fermer
                  </Button>
                </>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>

      <PayrollPreflightAcknowledgeDialog
        open={ackOpen}
        onOpenChange={setAckOpen}
        data={preflightData}
        acknowledged={ackConfirmed}
        onAcknowledgedChange={setAckConfirmed}
        onConfirm={handleAcknowledgeAndGenerate}
        isSubmitting={ackSubmitting}
      />
    </>
  );
}

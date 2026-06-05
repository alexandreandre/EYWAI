import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Loader2, PartyPopper } from 'lucide-react';
import { PayrollProgressBar } from '@/features/payroll/components/PayrollProgressBar';
import { usePayrollGeneration } from '@/features/payroll/hooks/usePayrollGeneration';
import type { SimpleEmployee } from '@/features/dashboard/types';

interface GeneratePayrollModalProps {
  isOpen: boolean;
  onClose: () => void;
  employees: SimpleEmployee[];
}

type Phase = 'select' | 'running' | 'done';

export function GeneratePayrollModal({ isOpen, onClose, employees }: GeneratePayrollModalProps) {
  const [selectedEmployees, setSelectedEmployees] = useState<Set<string>>(new Set());
  const [selectedMonth, setSelectedMonth] = useState<string>('');
  const [uiPhase, setUiPhase] = useState<Phase>('select');
  const feedRef = useRef<HTMLDivElement>(null);

  const generation = usePayrollGeneration();

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
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [generation.log, generation.currentLabel]);

  useEffect(() => () => generation.dismiss(), []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedEmployees(new Set(employees.map((e) => e.id)));
    } else {
      setSelectedEmployees(new Set());
    }
  };

  const handleSelect = (id: string, checked: boolean) => {
    const newSet = new Set(selectedEmployees);
    if (checked) {
      newSet.add(id);
    } else {
      newSet.delete(id);
    }
    setSelectedEmployees(newSet);
  };

  const handleGenerate = () => {
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

  const handleReset = () => {
    generation.reset();
    setUiPhase('select');
  };

  const handleClose = () => {
    generation.dismiss();
    onClose();
  };

  const isAllSelected = employees.length > 0 && selectedEmployees.size === employees.length;
  const successCount = generation.log.filter((l) => l.status === 'success').length;
  const errorCount = generation.log.filter((l) => l.status === 'error').length;

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open && uiPhase !== 'running') handleClose();
      }}
    >
      <DialogContent className="max-w-md p-0" hideClose={uiPhase === 'running'}>
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

            <Command className="p-2">
              <CommandInput placeholder="Rechercher un employé..." />
              <CommandList className="max-h-[300px] overflow-y-auto">
                <CommandEmpty>Aucun employé trouvé.</CommandEmpty>
                <CommandGroup>
                  <CommandItem
                    onSelect={() => handleSelectAll(!isAllSelected)}
                    className="flex items-center gap-3"
                  >
                    <Checkbox checked={isAllSelected} onCheckedChange={handleSelectAll} />
                    <label className="font-medium">Tout sélectionner</label>
                  </CommandItem>
                  {employees.map((emp) => (
                    <CommandItem
                      key={emp.id}
                      value={`${emp.first_name} ${emp.last_name}`}
                      onSelect={() => handleSelect(emp.id, !selectedEmployees.has(emp.id))}
                      className="flex items-center gap-3"
                    >
                      <Checkbox
                        checked={selectedEmployees.has(emp.id)}
                        onCheckedChange={(checked) => handleSelect(emp.id, !!checked)}
                      />
                      <label>{emp.first_name} {emp.last_name}</label>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>

            <div className="p-6 pt-2 flex justify-end gap-2">
              <Button variant="ghost" onClick={handleClose}>
                Annuler
              </Button>
              <Button
                className="bg-cyan-500 hover:bg-cyan-600 text-white"
                onClick={handleGenerate}
                disabled={selectedEmployees.size === 0 || !selectedMonth}
              >
                Générer ({selectedEmployees.size})
              </Button>
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
                {errorCount === 0 ? (
                  <>
                    <PartyPopper className="h-5 w-5 shrink-0 text-green-600" />
                    <span className="font-medium text-green-700">
                      {successCount} bulletin{successCount > 1 ? 's' : ''} généré
                      {successCount > 1 ? 's' : ''} avec succès.
                    </span>
                  </>
                ) : (
                  <span className="text-foreground">
                    <span className="font-medium text-green-700">
                      {successCount} réussi{successCount > 1 ? 's' : ''}
                    </span>
                    {' · '}
                    <span className="font-medium text-red-600">
                      {errorCount} en échec
                    </span>
                  </span>
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
  );
}

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Copy,
  Download,
  LayoutTemplate,
  Loader2,
  Calculator,
  Equal,
} from 'lucide-react';
import * as calendarApi from '@/api/calendar';
import { runWithConcurrency } from '@/lib/concurrency';
import { useToast } from '@/components/ui/use-toast';
import { exportOverviewCsv } from '@/lib/schedulesOverview';
import type { EmployeeCalendarOverviewRow } from '@/lib/schedulesOverview';

interface CalendarBulkActionsBarProps {
  selectedCount: number;
  selectedEmployeeIds: string[];
  year: number;
  month: number;
  overviewRows: EmployeeCalendarOverviewRow[];
  onClearSelection: () => void;
  onOpenApplyModel: () => void;
  onActionComplete: () => void;
}

export function CalendarBulkActionsBar({
  selectedCount,
  selectedEmployeeIds,
  year,
  month,
  overviewRows,
  onClearSelection,
  onOpenApplyModel,
  onActionComplete,
}: CalendarBulkActionsBarProps) {
  const { toast } = useToast();
  const [busy, setBusy] = useState<string | null>(null);

  const selectedRows = overviewRows.filter((r) =>
    selectedEmployeeIds.includes(r.employee.id)
  );

  const copyPreviousMonth = async () => {
    setBusy('copy');
    let prevMonth = month - 1;
    let prevYear = year;
    if (prevMonth < 1) {
      prevMonth = 12;
      prevYear -= 1;
    }

    try {
      const tasks = selectedEmployeeIds.map((id) => async () => {
        const [prevRes, currentPlannedRes] = await Promise.all([
          calendarApi.getPlannedCalendar(id, prevYear, prevMonth),
          calendarApi.getPlannedCalendar(id, year, month),
        ]);
        const prevData = prevRes.data.calendrier_prevu ?? [];
        const currentData = currentPlannedRes.data.calendrier_prevu ?? [];
        const daysInMonth = new Date(year, month, 0).getDate();

        const merged = [];
        for (let jour = 1; jour <= daysInMonth; jour++) {
          const fromPrev = prevData.find(
            (p: { jour: number }) => p.jour === jour
          );
          const existing = currentData.find(
            (p: { jour: number }) => p.jour === jour
          );
          merged.push(
            fromPrev
              ? { ...fromPrev, jour }
              : existing ?? { jour, type: 'travail', heures_prevues: null }
          );
        }

        await calendarApi.updatePlannedCalendar(id, year, month, merged);
      });

      await runWithConcurrency(tasks, 5);
      toast({
        title: 'Mois précédent copié',
        description: `Planning copié pour ${selectedEmployeeIds.length} employé(s).`,
      });
      onActionComplete();
    } catch {
      toast({
        title: 'Erreur',
        description: 'Impossible de copier le mois précédent.',
        variant: 'destructive',
      });
    } finally {
      setBusy(null);
    }
  };

  const copyPlannedToActual = async () => {
    setBusy('equal');
    try {
      const tasks = selectedEmployeeIds.map((id) => async () => {
        const row = overviewRows.find((r) => r.employee.id === id);
        if (!row) return;
        const actual = row.planned.map((p) => ({
          jour: p.jour,
          type: p.type,
          heures_faites: p.heures_prevues,
        }));
        await calendarApi.updateActualHours(id, year, month, actual);
      });
      await runWithConcurrency(tasks, 5);
      toast({
        title: 'Heures réelles mises à jour',
        description: `Réel = prévu pour ${selectedEmployeeIds.length} employé(s).`,
      });
      onActionComplete();
    } catch {
      toast({
        title: 'Erreur',
        description: 'Impossible de copier le prévu en réel.',
        variant: 'destructive',
      });
    } finally {
      setBusy(null);
    }
  };

  const calculatePayrollSelected = async () => {
    setBusy('payroll');
    try {
      const tasks = selectedEmployeeIds.map((id) => () =>
        calendarApi.calculatePayrollEvents(id, year, month)
      );
      await runWithConcurrency(tasks, 5);
      toast({
        title: 'Calcul paie lancé',
        description: `${selectedEmployeeIds.length} employé(s) traité(s).`,
      });
    } catch {
      toast({
        title: 'Erreur',
        description: 'Certains calculs paie ont échoué.',
        variant: 'destructive',
      });
    } finally {
      setBusy(null);
    }
  };

  const handleExport = () => {
    exportOverviewCsv(selectedRows, year, month);
    toast({ title: 'Export CSV', description: 'Fichier téléchargé.' });
  };

  if (selectedCount === 0) return null;

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 w-[min(96vw,900px)] bg-card border rounded-xl shadow-2xl p-3 flex flex-wrap items-center gap-2">
      <p className="text-sm font-medium pr-2 border-r mr-1">
        {selectedCount} sélectionné{selectedCount > 1 ? 's' : ''}
      </p>

      <Button size="sm" variant="outline" onClick={onOpenApplyModel} disabled={!!busy}>
        <LayoutTemplate className="mr-1.5 h-4 w-4" />
        Appliquer modèle
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => void copyPreviousMonth()}
        disabled={!!busy}
      >
        {busy === 'copy' ? (
          <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
        ) : (
          <Copy className="mr-1.5 h-4 w-4" />
        )}
        Copier mois précédent
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => void copyPlannedToActual()}
        disabled={!!busy}
      >
        {busy === 'equal' ? (
          <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
        ) : (
          <Equal className="mr-1.5 h-4 w-4" />
        )}
        Réel = prévu
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => void calculatePayrollSelected()}
        disabled={!!busy}
      >
        {busy === 'payroll' ? (
          <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
        ) : (
          <Calculator className="mr-1.5 h-4 w-4" />
        )}
        Calcul paie
      </Button>
      <Button size="sm" variant="outline" onClick={handleExport} disabled={!!busy}>
        <Download className="mr-1.5 h-4 w-4" />
        Export CSV
      </Button>
      <Button size="sm" variant="ghost" onClick={onClearSelection} className="ml-auto">
        Annuler
      </Button>
    </div>
  );
}

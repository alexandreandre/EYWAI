import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ToastAction } from '@/components/ui/toast';
import {
  Copy,
  Download,
  LayoutTemplate,
  Loader2,
  CopyCheck,
  Undo2,
  ScanLine,
} from 'lucide-react';
import * as calendarApi from '@/api/calendar';
import { useCompany } from '@/contexts/CompanyContext';
import { runWithConcurrency } from '@/lib/concurrency';
import { useToast } from '@/components/ui/use-toast';
import { exportOverviewCsv } from '@/lib/schedulesOverview';
import type { EmployeeCalendarOverviewRow } from '@/lib/schedulesOverview';
import {
  restoreActualSnapshots,
  restorePlannedSnapshots,
  type ActualSnapshot,
  type PlannedSnapshot,
} from '@/lib/calendarBulkUndo';

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
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.id ?? '';
  const [busy, setBusy] = useState<string | null>(null);

  const selectedRows = overviewRows.filter((r) =>
    selectedEmployeeIds.includes(r.employee.id)
  );

  const runUndo = async (restore: () => Promise<void>) => {
    setBusy('undo');
    try {
      await restore();
      toast({
        title: 'Action annulée',
        description: "L'état précédent a été restauré.",
      });
      onActionComplete();
    } catch {
      toast({
        title: 'Erreur',
        description: "Impossible d'annuler l'action.",
        variant: 'destructive',
      });
    } finally {
      setBusy(null);
    }
  };

  const undoToastAction = (restore: () => Promise<void>) => (
    <ToastAction
      altText="Annuler la dernière action"
      onClick={() => void runUndo(restore)}
    >
      <Undo2 className="mr-1 h-3.5 w-3.5" />
      Annuler
    </ToastAction>
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
      const snapshots: PlannedSnapshot[] = [];
      const tasks = selectedEmployeeIds.map((id) => async () => {
        const [prevRes, currentPlannedRes] = await Promise.all([
          calendarApi.getPlannedCalendar(id, prevYear, prevMonth),
          calendarApi.getPlannedCalendar(id, year, month),
        ]);
        const prevData = prevRes.data.calendrier_prevu ?? [];
        const currentData = currentPlannedRes.data.calendrier_prevu ?? [];
        snapshots.push({ id, planned: currentData });
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
        action: undoToastAction(() =>
          restorePlannedSnapshots(snapshots, year, month)
        ),
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
      const snapshots: ActualSnapshot[] = [];
      const tasks = selectedEmployeeIds.map((id) => async () => {
        const row = overviewRows.find((r) => r.employee.id === id);
        if (!row) return;
        const prevActualRes = await calendarApi.getActualHours(id, year, month);
        snapshots.push({
          id,
          actual: prevActualRes.data.calendrier_reel ?? [],
        });
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
        action: undoToastAction(() =>
          restoreActualSnapshots(snapshots, year, month)
        ),
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

  const importFromBadgeuse = async () => {
    if (!companyId) {
      toast({
        title: 'Erreur',
        description: 'Aucune entreprise active.',
        variant: 'destructive',
      });
      return;
    }
    setBusy('badgeuse');
    try {
      const res = await calendarApi.importBadgeuseActualHoursBulk(
        companyId,
        selectedEmployeeIds,
        year,
        month
      );
      const payload = res.data;
      toast({
        title: 'Badgeuse importée',
        description: `${payload.total_days_updated} jour(s) mis à jour pour ${payload.employees_processed} employé(s).`,
      });
      if (payload.errors?.length) {
        toast({
          title: 'Certains employés ignorés',
          description: payload.errors.map((e) => e.message).join(' '),
          variant: 'destructive',
        });
      }
      onActionComplete();
    } catch {
      toast({
        title: 'Erreur',
        description: "Impossible d'importer depuis la badgeuse.",
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
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 w-[min(98vw,1280px)] bg-card border rounded-xl shadow-2xl px-3 py-2 flex flex-nowrap items-center gap-1.5 overflow-x-auto">
      <p className="text-sm font-medium pr-2 border-r mr-1 shrink-0 whitespace-nowrap">
        {selectedCount} sélectionné{selectedCount > 1 ? 's' : ''}
      </p>

      <Button
        size="sm"
        variant="outline"
        onClick={onOpenApplyModel}
        disabled={!!busy}
        className="shrink-0 whitespace-nowrap"
      >
        <LayoutTemplate className="mr-1.5 h-4 w-4" />
        Appliquer modèle
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => void copyPreviousMonth()}
        disabled={!!busy}
        className="shrink-0 whitespace-nowrap"
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
        className="shrink-0 whitespace-nowrap"
      >
        {busy === 'equal' ? (
          <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
        ) : (
          <CopyCheck className="mr-1.5 h-4 w-4" />
        )}
        Réel = prévu
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => void importFromBadgeuse()}
        disabled={!!busy || !companyId}
        className="shrink-0 whitespace-nowrap"
      >
        {busy === 'badgeuse' ? (
          <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
        ) : (
          <ScanLine className="mr-1.5 h-4 w-4" />
        )}
        Réel depuis badgeuse
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={handleExport}
        disabled={!!busy}
        className="shrink-0 whitespace-nowrap"
      >
        <Download className="mr-1.5 h-4 w-4" />
        Export CSV
      </Button>
      <Button
        size="sm"
        variant="ghost"
        onClick={onClearSelection}
        className="ml-auto shrink-0 whitespace-nowrap"
      >
        Annuler
      </Button>
    </div>
  );
}

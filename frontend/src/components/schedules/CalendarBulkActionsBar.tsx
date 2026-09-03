import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ToastAction } from '@/components/ui/toast';
import {
  Copy,
  LayoutTemplate,
  Loader2,
  CopyCheck,
  Sparkles,
  Undo2,
  ScanLine,
} from 'lucide-react';
import * as calendarApi from '@/api/calendar';
import { useCompany } from '@/contexts/CompanyContext';
import { runWithConcurrency } from '@/lib/concurrency';
import { useToast } from '@/components/ui/use-toast';
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
  /** Ouvre le remplissage IA ciblé sur la sélection courante. */
  onFillWithAi: (ids: string[]) => void;
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
  onFillWithAi,
}: CalendarBulkActionsBarProps) {
  const { toast } = useToast();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.id ?? '';
  const [busy, setBusy] = useState<string | null>(null);

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
      let preservedCount = 0;
      let requalifiedCount = 0;
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
            (p: { jour: number; origine?: string | null }) => p.jour === jour
          );
          // Un jour du mois cible issu d'une absence validée n'est jamais
          // recouvert par la copie : il reste tel quel.
          if (existing?.origine === 'absence') {
            preservedCount += 1;
            merged.push(existing);
            continue;
          }
          merged.push(
            fromPrev
              ? { ...fromPrev, jour }
              : existing ?? { jour, type: 'travail', heures_prevues: null }
          );
        }

        const res = await calendarApi.updatePlannedCalendar(id, year, month, merged);
        // Défensif : `warnings` est absent tant que le backend ne le renvoie pas.
        requalifiedCount += (res.data?.warnings ?? []).filter(
          (w) => w.code === 'absence_validee_requalifiee'
        ).length;
      });

      await runWithConcurrency(tasks, 5);
      const preservedNote =
        preservedCount > 0
          ? ` ${preservedCount} jour(s) d'absence validée conservé(s).`
          : '';
      if (requalifiedCount > 0) {
        toast({
          title: 'Mois précédent copié — absences requalifiées',
          description: `Ce changement requalifie ${requalifiedCount} jour(s) d'absence validée.${preservedNote}`,
          variant: 'warning',
          action: undoToastAction(() =>
            restorePlannedSnapshots(snapshots, year, month)
          ),
        });
      } else {
        toast({
          title: 'Mois précédent copié',
          description: `Planning copié pour ${selectedEmployeeIds.length} employé(s).${preservedNote}`,
          action: undoToastAction(() =>
            restorePlannedSnapshots(snapshots, year, month)
          ),
        });
      }
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
        // Le réel ne se copie que sur les jours de travail : un réel > 0 sur
        // un jour congé/arrêt compte les heures comme travaillées en paie et
        // efface l'absence du bulletin (analyzer).
        const actual = row.planned.map((p) => ({
          jour: p.jour,
          type: p.type,
          heures_faites:
            p.type === 'travail' || p.type === 'work' ? p.heures_prevues : 0,
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

  if (selectedCount === 0) return null;

  const outlineAction =
    'shrink-0 whitespace-nowrap border-2 border-foreground/25 bg-background shadow-none';

  return (
    <div
      role="toolbar"
      aria-label="Saisie rapide"
      className="fixed bottom-4 left-1/2 z-50 flex w-max max-w-[min(98vw,1280px)] -translate-x-1/2 flex-nowrap items-center gap-1.5 overflow-x-auto rounded-xl border-2 border-foreground/40 bg-background px-3 py-2.5 shadow-[0_12px_36px_-8px_hsl(215_25%_15%_/_0.35)]"
    >
      <p className="shrink-0 whitespace-nowrap rounded-md bg-primary px-2.5 py-1 text-sm font-semibold tabular-nums text-primary-foreground">
        {selectedCount} sélectionné{selectedCount > 1 ? 's' : ''}
      </p>
      <span aria-hidden className="mx-0.5 h-7 w-px shrink-0 bg-foreground/20" />

      <Button
        size="sm"
        variant="outline"
        onClick={onOpenApplyModel}
        disabled={!!busy}
        className={outlineAction}
        title="Rythme de semaine : heures prévues, heures faites, ou les deux"
      >
        <LayoutTemplate className="mr-1.5 h-4 w-4" />
        Appliquer modèle
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => void copyPreviousMonth()}
        disabled={!!busy}
        className={outlineAction}
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
        className={outlineAction}
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
        className={outlineAction}
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
        onClick={() => onFillWithAi(selectedEmployeeIds)}
        disabled={!!busy}
        className="shrink-0 whitespace-nowrap"
      >
        <Sparkles className="mr-1.5 h-4 w-4" />
        Remplir par l&apos;IA ({selectedCount})
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={onClearSelection}
        className="shrink-0 whitespace-nowrap border-2 border-foreground/20 text-muted-foreground"
      >
        Annuler
      </Button>
    </div>
  );
}

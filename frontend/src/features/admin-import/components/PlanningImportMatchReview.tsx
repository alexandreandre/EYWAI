import { useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import {
  applyPlanningImportMappings,
  type PlanningImportReviewItem,
  type PlanningImportSummary,
} from '@/api/adminImport';
import type { RosterEmployee } from '@/api/calendar';
import { EmployeeAssociateCombobox } from '@/components/schedules/assisted-fill/EmployeeAssociateCombobox';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useToast } from '@/hooks/use-toast';
import { getUserErrorMessage } from '@/lib/errorMessages';

function statusBadge(status: PlanningImportReviewItem['review_status']) {
  if (status === 'warning') {
    return (
      <Badge variant="secondary" className="bg-amber-100 text-amber-900">
        À vérifier
      </Badge>
    );
  }
  return <Badge variant="destructive">À associer</Badge>;
}

function buildOptimisticSummary(
  summary: PlanningImportSummary,
  mapping: { raw_name: string; employee_id: string },
): PlanningImportSummary {
  const assigned = new Set(summary.assigned_employee_ids ?? []);
  assigned.add(mapping.employee_id);

  const reviewItems = (summary.review_items ?? []).filter(
    (item) => item.raw_name !== mapping.raw_name,
  );

  const wasError = summary.review_items?.some(
    (item) => item.raw_name === mapping.raw_name && item.review_status === 'error',
  );
  const wasWarning = summary.review_items?.some(
    (item) => item.raw_name === mapping.raw_name && item.review_status === 'warning',
  );

  return {
    ...summary,
    assigned_employee_ids: [...assigned].sort(),
    employees_ok: (summary.employees_ok ?? 0) + 1,
    employees_error: Math.max(0, (summary.employees_error ?? 0) - (wasError ? 1 : 0)),
    employees_warning: Math.max(0, (summary.employees_warning ?? 0) - (wasWarning ? 1 : 0)),
    employees_importable: (summary.employees_importable ?? 0) + (wasError ? 1 : 0),
    review_items: reviewItems,
    review_items_truncated: summary.review_items_truncated,
    validation_status:
      reviewItems.length === 0
        ? 'ok'
        : reviewItems.some((item) => item.review_status === 'error')
          ? 'warning'
          : 'warning',
  };
}

type Props = {
  batchId: string;
  companyId: string;
  summary: PlanningImportSummary;
  roster: RosterEmployee[];
  onSummaryUpdated: (summary: PlanningImportSummary) => void;
};

export function PlanningImportMatchReview({
  batchId,
  companyId,
  summary,
  roster,
  onSummaryUpdated,
}: Props) {
  const { toast } = useToast();
  const [pendingSheet, setPendingSheet] = useState<string | null>(null);

  const items = summary.review_items;
  const assignedEmployeeIds = summary.assigned_employee_ids ?? [];

  const rosterById = useMemo(
    () => new Map(roster.map((emp) => [emp.id, emp])),
    [roster],
  );

  const applyMutation = useMutation({
    mutationFn: async (mapping: { raw_name: string; employee_id: string }) =>
      applyPlanningImportMappings(batchId, companyId, [mapping]),
    onMutate: (mapping) => {
      setPendingSheet(mapping.raw_name);
      const previous = summary;
      onSummaryUpdated(buildOptimisticSummary(summary, mapping));
      return { previous };
    },
    onSuccess: (data, variables) => {
      onSummaryUpdated(data.summary);
      toast({
        title: 'Feuille associée',
        description: `« ${variables.raw_name} » rapprochée du dossier.`,
      });
    },
    onError: (error, _variables, context) => {
      if (context?.previous) {
        onSummaryUpdated(context.previous);
      }
      toast({ title: 'Erreur', description: getUserErrorMessage(error), variant: 'destructive' });
    },
    onSettled: () => setPendingSheet(null),
  });

  if (items.length === 0) return null;

  return (
    <div className="space-y-2 rounded-lg border bg-background p-3">
      <div>
        <p className="text-sm font-medium">Rapprochement des feuilles Excel</p>
        <p className="text-xs text-muted-foreground">
          Seuls les salariés encore disponibles sont proposés. Les suggestions tiennent compte du
          Sommaire Excel et des feuilles déjà rapprochées.
        </p>
      </div>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Feuille Excel</TableHead>
              <TableHead className="w-[100px]">Statut</TableHead>
              <TableHead>Salarié EYWAI</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => {
              const isPending = pendingSheet === item.raw_name && applyMutation.isPending;
              const preferredIds = (item.suggested_employee_ids ?? []).filter(
                (id) => !assignedEmployeeIds.includes(id),
              );
              const topSuggestionId = preferredIds[0] ?? null;
              const topSuggestion = topSuggestionId ? rosterById.get(topSuggestionId) : undefined;
              const suggestionLabels = preferredIds
                .map((id) => rosterById.get(id))
                .filter(Boolean)
                .map((emp) => `${emp!.last_name} ${emp!.first_name}`);

              return (
                <TableRow key={item.raw_name}>
                  <TableCell className="align-top">
                    <div className="font-medium">{item.raw_name}</div>
                    <p className="mt-0.5 text-xs text-muted-foreground">{item.message}</p>
                    {item.sommaire_hint ? (
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        Sommaire : {item.sommaire_hint}
                      </p>
                    ) : null}
                    {suggestionLabels.length > 0 ? (
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        Suggestions : {suggestionLabels.join(', ')}
                      </p>
                    ) : null}
                  </TableCell>
                  <TableCell className="align-top">{statusBadge(item.review_status)}</TableCell>
                  <TableCell className="align-top">
                    <div className="flex flex-wrap items-center gap-2">
                      {isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                      ) : null}
                      {topSuggestion && preferredIds.length === 1 ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="secondary"
                          className="h-7 text-xs"
                          disabled={applyMutation.isPending}
                          onClick={() => {
                            applyMutation.mutate({
                              raw_name: item.raw_name,
                              employee_id: topSuggestion.id,
                            });
                          }}
                        >
                          Associer {topSuggestion.last_name} {topSuggestion.first_name}
                        </Button>
                      ) : null}
                      <EmployeeAssociateCombobox
                        roster={roster}
                        value={item.employee_id ?? null}
                        excludeEmployeeIds={assignedEmployeeIds}
                        includeSelectedWhenExcluded={false}
                        preferredEmployeeIds={preferredIds}
                        placeholder="Choisir un salarié…"
                        onSelect={(employeeId) => {
                          applyMutation.mutate({
                            raw_name: item.raw_name,
                            employee_id: employeeId,
                          });
                        }}
                      />
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      {summary.review_items_truncated > 0 ? (
        <p className="text-xs text-muted-foreground">
          +{summary.review_items_truncated} autre(s) feuille(s) non affichée(s).
        </p>
      ) : null}
    </div>
  );
}

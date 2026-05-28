import { Trash2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { Shift } from "@/api/planning";
import {
  apiErrorMessage,
  formatDateFrCell,
  formatHourRange,
  replacerDisplayName,
} from "@/features/planning/utils/planningUtils";

interface Props {
  isRH: boolean;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  replacements: Shift[];
  deletePending: boolean;
  onAdd: () => void;
  onDelete: (id: string) => void;
}

export function PlanningReplacementsView({
  isRH,
  isLoading,
  isError,
  error,
  replacements,
  deletePending,
  onAdd,
  onDelete,
}: Props) {
  if (!isRH) {
    return (
      <div className="rounded-md border bg-muted/30 p-6 text-sm text-muted-foreground">
        La vue remplacements est réservée aux accès RH.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-lg font-semibold tracking-tight">Gestion des remplacements</h2>
        <Button type="button" size="sm" onClick={onAdd}>
          <Plus className="mr-1 h-4 w-4" />
          Planifier un remplacement
        </Button>
      </div>
      {isLoading ? (
        <div className="space-y-2 rounded-md border p-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : isError ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          {apiErrorMessage(error)}
        </div>
      ) : replacements.length === 0 ? (
        <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
          Aucun remplacement ce mois-ci.
        </div>
      ) : (
        <div className="w-full overflow-x-auto rounded-md border">
          <table className="w-full min-w-[880px] border-collapse text-sm">
            <thead>
              <tr className="border-b bg-muted/40">
                <th className="border-r px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Date
                </th>
                <th className="border-r px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Remplaçant
                </th>
                <th className="border-r px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Remplacé
                </th>
                <th className="border-r px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Horaires
                </th>
                <th className="border-r px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Motif
                </th>
                <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {replacements.map((s) => (
                <tr key={s.id} className="border-b last:border-b-0">
                  <td className="border-r px-3 py-2 align-top text-muted-foreground">
                    {formatDateFrCell(s.shift_date)}
                  </td>
                  <td className="border-r px-3 py-2 align-top font-medium">
                    {replacerDisplayName(s)}
                  </td>
                  <td className="border-r px-3 py-2 align-top">
                    {s.original_employee_name ?? '—'}
                  </td>
                  <td className="border-r px-3 py-2 align-top tabular-nums">
                    {formatHourRange(s)}
                  </td>
                  <td className="border-r px-3 py-2 align-top text-muted-foreground">
                    {s.replacement_reason?.trim() ? s.replacement_reason : '—'}
                  </td>
                  <td className="px-3 py-2 align-top text-right">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                      disabled={deletePending || s.is_locked}
                      title={s.is_locked ? 'Shift verrouillé' : 'Supprimer'}
                      onClick={() => {
                        if (!s.is_locked) onDelete(s.id);
                      }}
                      aria-label="Supprimer le remplacement"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

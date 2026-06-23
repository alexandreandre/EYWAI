import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import type { WorkforceGap, WorkforceReconciliationSummary, WorkforceResolution } from '@/api/dsnImport';
import { WorkforceGapRow } from './WorkforceGapRow';
import { WorkforceReconciliationSummary as WorkforceReconciliationSummaryCard } from './WorkforceReconciliationSummary';

type Props = {
  batchId: string;
  reconciliation: WorkforceReconciliationSummary;
  resolutions: Record<string, WorkforceResolution>;
  onResolutionChange: (resolution: WorkforceResolution) => void;
  onResolutionClear?: (gapId: string) => void;
  onBack: () => void;
  onCommit: () => void;
  canCommit: boolean;
  blockReason: string | null;
  saving?: boolean;
  committing?: boolean;
};

export function WorkforceReconciliationStep({
  batchId,
  reconciliation,
  resolutions,
  onResolutionChange,
  onResolutionClear,
  onBack,
  onCommit,
  canCommit,
  blockReason,
  saving,
  committing,
}: Props) {
  const gaps = reconciliation.gaps ?? [];

  return (
    <div className="space-y-6 pb-24">
      <WorkforceReconciliationSummaryCard reconciliation={reconciliation} />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Décisions par salarié</CardTitle>
          <CardDescription>
            Chaque écart doit avoir une décision avant de valider l&apos;import.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {gaps.map((gap: WorkforceGap) => (
            <WorkforceGapRow
              key={gap.gap_id}
              gap={gap}
              batchId={batchId}
              resolution={resolutions[gap.gap_id] ?? gap.resolution ?? undefined}
              onResolutionChange={onResolutionChange}
              onResolutionClear={onResolutionClear}
            />
          ))}
        </CardContent>
      </Card>

      <div className="fixed inset-x-0 bottom-0 z-40 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3">
          <Button variant="ghost" size="sm" onClick={onBack}>
            Retour à l&apos;analyse
          </Button>
          <div className="flex flex-col items-end gap-1">
            {blockReason && (
              <p className="max-w-md text-right text-xs text-muted-foreground">{blockReason}</p>
            )}
            <Button onClick={onCommit} disabled={!canCommit || committing}>
              {(committing || saving) && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Valider l&apos;import
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

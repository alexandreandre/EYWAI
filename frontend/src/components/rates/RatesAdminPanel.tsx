import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, ChevronDown, ShieldCheck } from 'lucide-react';

import type { RatesResponse } from '@/api/rates';
import { listAlerts, listPendingChanges } from '@/api/scraping';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { MonthlyReviewTab } from '@/features/admin/components/scraping/MonthlyReviewTab';
import { RatesManualEditDialog } from '@/components/rates/RatesManualEditDialog';

type Props = {
  data: RatesResponse;
  onManualSaved?: () => void;
};

export function RatesAdminPanel({ data, onManualSaved }: Props) {
  const queryClient = useQueryClient();
  const [reviewOpen, setReviewOpen] = useState(false);

  const pendingQuery = useQuery({
    queryKey: ['rates-admin', 'pending-count'],
    queryFn: () => listPendingChanges({ status: 'pending' }),
    staleTime: 30_000,
  });

  const criticalAlertsQuery = useQuery({
    queryKey: ['rates-admin', 'critical-alerts'],
    queryFn: () => listAlerts({ is_resolved: false, severity: 'critical', limit: 50 }),
    staleTime: 30_000,
  });

  const pendingCount = pendingQuery.data?.total ?? pendingQuery.data?.pending?.length ?? 0;
  const criticalCount =
    criticalAlertsQuery.data?.total ?? criticalAlertsQuery.data?.alerts?.length ?? 0;
  const hasReviewItems = pendingCount > 0 || criticalCount > 0;

  const handleManualSaved = () => {
    void queryClient.invalidateQueries({ queryKey: ['rates-admin'] });
    onManualSaved?.();
  };

  return (
    <Card className="border-primary/30 bg-primary/[0.02]">
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldCheck className="h-4 w-4 text-primary" />
            Espace administrateur
          </CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            <RatesManualEditDialog data={data} onSaved={handleManualSaved} />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {hasReviewItems ? (
          <>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              {pendingCount > 0 && (
                <Badge variant="default" className="bg-purple-600 hover:bg-purple-600">
                  {pendingCount} changement(s) en attente de validation
                </Badge>
              )}
              {criticalCount > 0 && (
                <Badge variant="destructive" className="gap-1">
                  <AlertTriangle className="h-3 w-3" />
                  {criticalCount} alerte(s) critique(s)
                </Badge>
              )}
            </div>

            <Collapsible open={reviewOpen} onOpenChange={setReviewOpen}>
              <CollapsibleTrigger asChild>
                <Button variant="outline" size="sm" className="w-full justify-between sm:w-auto">
                  Validation & alertes
                  <ChevronDown
                    className={`ml-2 h-4 w-4 transition-transform ${reviewOpen ? 'rotate-180' : ''}`}
                  />
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="pt-4">
                <MonthlyReviewTab />
              </CollapsibleContent>
            </Collapsible>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            Aucun taux scrapé problématique en attente — le référentiel est à jour.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

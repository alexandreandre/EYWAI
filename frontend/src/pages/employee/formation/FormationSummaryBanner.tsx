import { SharkFinLoader } from '@/components/SharkFinLoader';

import { Button } from "@/components/ui/button";
import type { EmployeeFormationTabId } from "@/lib/employeeFormationUtils";
import type { FormationSummaryCounts } from "@/hooks/useEmployeeFormationSummary";
import { cn } from "@/lib/utils";

type FormationSummaryBannerProps = {
  counts: FormationSummaryCounts;
  onNavigateTab: (tab: EmployeeFormationTabId) => void;
};

type SummaryItem = {
  tab: EmployeeFormationTabId;
  label: string;
  count: number;
};

export function FormationSummaryBanner({ counts, onNavigateTab }: FormationSummaryBannerProps) {
  if (counts.isLoading) {
    return (
      <div className="rounded-lg border bg-muted/30 px-4 py-2">
        <SharkFinLoader variant="compact" label="Chargement de votre synthèse…" />
      </div>
    );
  }

  const items: SummaryItem[] = [];
  if (counts.reviewsAction > 0) {
    items.push({
      tab: "entretiens",
      label:
        counts.reviewsAction === 1
          ? "1 entretien à traiter"
          : `${counts.reviewsAction} entretiens à traiter`,
      count: counts.reviewsAction,
    });
  }
  if (counts.enrollmentsPending > 0) {
    items.push({
      tab: "formations",
      label:
        counts.enrollmentsPending === 1
          ? "1 demande en attente"
          : `${counts.enrollmentsPending} demandes en attente`,
      count: counts.enrollmentsPending,
    });
  }
  if (counts.certsWatch > 0) {
    items.push({
      tab: "habilitations",
      label:
        counts.certsWatch === 1
          ? "1 habilitation à surveiller"
          : `${counts.certsWatch} habilitations à surveiller`,
      count: counts.certsWatch,
    });
  }
  if (counts.onboardingIncomplete) {
    items.push({
      tab: "onboarding",
      label: "Onboarding en cours",
      count: 1,
    });
  }

  if (items.length === 0) {
    return (
      <p className="rounded-lg border border-dashed bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
        Aucune action en attente pour le moment.
      </p>
    );
  }

  return (
    <div className="flex flex-wrap gap-2" role="list" aria-label="Actions à traiter">
      {items.map((item) => (
        <Button
          key={item.tab}
          type="button"
          variant="secondary"
          size="sm"
          className={cn("h-auto py-1.5")}
          onClick={() => onNavigateTab(item.tab)}
          aria-label={`${item.label}, aller à l'onglet`}
        >
          <span className="mr-1.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-xs font-semibold text-primary-foreground">
            {item.count}
          </span>
          {item.label}
        </Button>
      ))}
    </div>
  );
}

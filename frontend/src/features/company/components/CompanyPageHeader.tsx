import { pageTitleClassName } from '@/components/layout';
import { Building2, Calendar, Download, Hash, Pencil } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { CompanyDetails } from "@/api/company";
import { AnalyticsPeriodControls } from "@/components/analytics/AnalyticsPeriodControls";
import type { PeriodSelection } from "@/lib/analyticsPeriod";

type CompanyPageHeaderProps = {
  company: CompanyDetails;
  period: PeriodSelection;
  onPeriodChange: (p: PeriodSelection) => void;
  periodLabel: string;
  isPremium?: boolean;
  canEdit: boolean;
  onEdit: () => void;
  onExport: () => void;
  exporting?: boolean;
};

export function CompanyPageHeader({
  company,
  period,
  onPeriodChange,
  periodLabel,
  isPremium,
  canEdit,
  onEdit,
  onExport,
  exporting,
}: CompanyPageHeaderProps): JSX.Element {
  const displayName = company.company_name?.trim() || "Mon Entreprise";

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className={`${pageTitleClassName} truncate`}>
              Mon Entreprise · {displayName}
            </h1>
            {isPremium ? (
              <Badge variant="secondary" className="shrink-0">
                Premium
              </Badge>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
            {company.raison_sociale ? (
              <span className="inline-flex items-center gap-1">
                <Building2 className="h-3.5 w-3.5 shrink-0" aria-hidden />
                {company.raison_sociale}
              </span>
            ) : null}
            {company.siret ? (
              <span className="inline-flex items-center gap-1 font-mono text-xs">
                <Hash className="h-3.5 w-3.5 shrink-0" aria-hidden />
                {company.siret}
              </span>
            ) : null}
            <span className="inline-flex items-center gap-1">
              <Calendar className="h-3.5 w-3.5 shrink-0" aria-hidden />
              {periodLabel}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={onExport} disabled={exporting}>
            <Download className="h-4 w-4 mr-2" />
            Export CSV
          </Button>
          {canEdit ? (
            <Button variant="outline" size="sm" onClick={onEdit}>
              <Pencil className="h-4 w-4 mr-2" />
              Modifier
            </Button>
          ) : null}
        </div>
      </div>
      <AnalyticsPeriodControls
        value={period}
        onChange={onPeriodChange}
        periodLabel={periodLabel}
        hint="Les indicateurs paie suivent la période sélectionnée."
      />
    </div>
  );
}

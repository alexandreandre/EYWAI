import { Building2, Download, FileText, Hash } from "lucide-react";
import { RhPageHeader } from "@/components/layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { CompanyDetails } from "@/api/company";
import { formatCollectiveAgreementLabel } from "@/features/company/lib/companyPageTabs";

type CompanyPageHeaderProps = {
  company: CompanyDetails;
  onExport: () => void;
  exporting?: boolean;
  onGoToPayrollTab: () => void;
};

export function CompanyPageHeader({
  company,
  onExport,
  exporting,
  onGoToPayrollTab,
}: CompanyPageHeaderProps): JSX.Element {
  const displayName = company.company_name?.trim() || "Mon Entreprise";
  const cc = formatCollectiveAgreementLabel(company.collective_agreement, company.idcc);

  return (
    <RhPageHeader
      title={displayName}
      description="Fiche, paramètres paie, mutuelle et modèles documentaires de l'entreprise."
      actions={
        <Button variant="outline" size="sm" onClick={onExport} disabled={exporting}>
          <Download className="h-4 w-4 mr-2" />
          Export CSV
        </Button>
      }
      afterDescription={
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-muted-foreground">
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
          <span className="inline-flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden />
            {cc.configured ? (
              <>
                <span className="text-foreground font-medium">{cc.label}</span>
                {cc.idcc ? (
                  <Badge variant="outline" className="text-xs font-mono">
                    IDCC {cc.idcc}
                  </Badge>
                ) : null}
              </>
            ) : (
              <Badge variant="outline" className="border-amber-400 text-amber-900 bg-amber-50">
                Convention collective non configurée
              </Badge>
            )}
            <button
              type="button"
              onClick={onGoToPayrollTab}
              className="text-xs text-primary underline-offset-2 hover:underline"
            >
              Gérer
            </button>
          </span>
        </div>
      }
    />
  );
}

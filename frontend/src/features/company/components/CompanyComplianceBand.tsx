import { AlertTriangle, CheckCircle2, FileText, Percent, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { CompanyDetails, CompanyOverview } from "@/api/company";
import { formatCollectiveAgreementLabel } from "@/features/company/lib/companyPageTabs";
import { cn } from "@/lib/utils";

type ComplianceAnchor =
  | "convention-collective"
  | "taux-at-mp"
  | "taux-vm"
  | "cse";

type Item = {
  key: string;
  label: string;
  ok: boolean;
  icon: typeof CheckCircle2;
  anchor?: ComplianceAnchor;
};

export function CompanyComplianceBand({
  compliance,
  company,
  onGoToPayrollSection,
}: {
  compliance: CompanyOverview["compliance"];
  company: CompanyDetails;
  onGoToPayrollSection: (anchor?: ComplianceAnchor) => void;
}): JSX.Element {
  const cc = formatCollectiveAgreementLabel(company.collective_agreement, company.idcc);
  const ccLabel = compliance.collective_agreement_configured
    ? cc.idcc
      ? `Convention · IDCC ${cc.idcc}`
      : cc.label.length > 32
        ? `${cc.label.slice(0, 32)}…`
        : cc.label
    : "Convention collective";

  const items: Item[] = [
    {
      key: "at_mp",
      label: "Taux AT/MP",
      ok: compliance.at_mp_configured,
      icon: Percent,
      anchor: "taux-at-mp",
    },
    {
      key: "vm",
      label: "Versement mobilité",
      ok: compliance.vm_configured,
      icon: Percent,
      anchor: "taux-vm",
    },
    {
      key: "cc",
      label: ccLabel,
      ok: compliance.collective_agreement_configured,
      icon: FileText,
      anchor: "convention-collective",
    },
    {
      key: "cse",
      label: compliance.cse_obligation ? "Obligations CSE (≥11)" : "CSE non requis",
      ok: !compliance.cse_obligation,
      icon: Users,
      anchor: "cse",
    },
  ];

  const hasWarning = items.some((i) => !i.ok);

  return (
    <div
      className={cn(
        "rounded-lg border p-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between",
        hasWarning ? "border-amber-200 bg-amber-50/80" : "border-border bg-muted/30",
      )}
    >
      <div className="flex items-center gap-2 text-sm font-medium">
        {hasWarning ? (
          <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" aria-hidden />
        ) : (
          <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" aria-hidden />
        )}
        Conformité & paramètres
      </div>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => onGoToPayrollSection(item.anchor)}
            className="inline-flex"
          >
            <Badge
              variant={item.ok ? "secondary" : "outline"}
              className={cn(
                "cursor-pointer gap-1 hover:opacity-90",
                !item.ok && "border-amber-400 text-amber-900 bg-amber-100/60",
              )}
            >
              <item.icon className="h-3 w-3" aria-hidden />
              {item.label}
              {item.ok ? " ✓" : " —"}
            </Badge>
          </button>
        ))}
        {hasWarning ? (
          <button
            type="button"
            onClick={() => onGoToPayrollSection("convention-collective")}
            className="text-xs text-primary underline-offset-2 hover:underline ml-1 self-center"
          >
            Compléter dans Paramètres paie
          </button>
        ) : null}
      </div>
    </div>
  );
}

export type { ComplianceAnchor };

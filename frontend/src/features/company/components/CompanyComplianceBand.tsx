import { AlertTriangle, CheckCircle2, FileText, Percent, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { CompanyOverview } from "@/api/company";
import { cn } from "@/lib/utils";

type Item = {
  key: string;
  label: string;
  ok: boolean;
  icon: typeof CheckCircle2;
};

export function CompanyComplianceBand({
  compliance,
  onGoToPayrollTab,
}: {
  compliance: CompanyOverview["compliance"];
  onGoToPayrollTab: () => void;
}): JSX.Element {
  const items: Item[] = [
    {
      key: "at_mp",
      label: "Taux AT/MP",
      ok: compliance.at_mp_configured,
      icon: Percent,
    },
    {
      key: "vm",
      label: "Versement mobilité",
      ok: compliance.vm_configured,
      icon: Percent,
    },
    {
      key: "cc",
      label: "Convention collective",
      ok: compliance.collective_agreement_configured,
      icon: FileText,
    },
    {
      key: "cse",
      label: compliance.cse_obligation ? "Obligations CSE (≥11)" : "CSE non requis",
      ok: !compliance.cse_obligation,
      icon: Users,
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
          <Badge
            key={item.key}
            variant={item.ok ? "secondary" : "outline"}
            className={cn(
              "cursor-default gap-1",
              !item.ok && "border-amber-400 text-amber-900 bg-amber-100/60",
            )}
          >
            <item.icon className="h-3 w-3" aria-hidden />
            {item.label}
            {item.ok ? " ✓" : " —"}
          </Badge>
        ))}
        {hasWarning ? (
          <button
            type="button"
            onClick={onGoToPayrollTab}
            className="text-xs text-primary underline-offset-2 hover:underline ml-1"
          >
            Compléter dans Paie
          </button>
        ) : null}
      </div>
    </div>
  );
}

import { useState } from "react";
import { Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

export interface OdBalanceDebug {
  period?: string;
  formula?: string;
  total_debit?: number;
  total_credit?: number;
  ecart?: number;
  heavier_side?: "debit" | "credit" | "balanced";
  interpretation?: string;
  payslips_included?: number;
  ecritures_lines?: number;
  debit_by_component?: Record<string, number>;
  credit_by_component?: Record<string, number>;
  payslip_source_totals?: Record<string, number>;
  reconciliation?: Record<string, number>;
  skipped_entries?: string[];
  gap_analysis?: {
    salary_equation?: {
      formula?: string;
      note_acomptes?: string;
      brut_bulletins?: number;
      cotisations_salariales_bulletins?: number;
      pas_bulletins?: number;
      credits_attendus_cote_salaire?: number;
      residu_equation?: number;
      residu_proche_ecart_od?: boolean;
    };
    likely_causes?: Array<{ code?: string; label?: string; montant?: number; montant_estime?: number }>;
    bulletins_sans_cotisations_extraites?: number;
    payslips_breakdown?: Array<{
      employee_name?: string;
      brut?: number;
      net_a_payer?: number;
      cotisations_salariales?: number;
      pas?: number;
      lignes_cotisations?: number;
    }>;
  };
}

function formatEuro(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
  }).format(value);
}

function ComponentList({
  title,
  items,
}: {
  title: string;
  items: Record<string, number> | undefined;
}) {
  if (!items || Object.keys(items).length === 0) return null;
  return (
    <div>
      <p className="text-muted-foreground text-xs font-medium">{title}</p>
      <ul className="mt-1 space-y-0.5 font-mono text-xs">
        {Object.entries(items).map(([key, value]) => (
          <li key={key} className="flex justify-between gap-2">
            <span>{key}</span>
            <span>{formatEuro(value)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function OdBalanceDebugPanel({ debug }: { debug: OdBalanceDebug }) {
  const { toast } = useToast();
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(debug, null, 2));
      setCopied(true);
      toast({ title: "Rapport copié", description: "Collez-le dans le chat pour analyse." });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast({
        title: "Copie impossible",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="bg-muted/40 mt-2 space-y-2 rounded-md border p-2.5">
      <p className="text-foreground text-xs font-medium">Diagnostic équilibre OD</p>
      {debug.interpretation ? (
        <p className="text-muted-foreground text-xs">{debug.interpretation}</p>
      ) : null}
      <div className="font-mono text-xs">
        <div className="flex justify-between gap-2">
          <span>Total débit</span>
          <span>{formatEuro(debug.total_debit)}</span>
        </div>
        <div className="flex justify-between gap-2">
          <span>Total crédit</span>
          <span>{formatEuro(debug.total_credit)}</span>
        </div>
        <div className="text-destructive flex justify-between gap-2 font-medium">
          <span>Écart |D − C|</span>
          <span>{formatEuro(debug.ecart)}</span>
        </div>
      </div>
      {debug.payslips_included !== undefined ? (
        <p className="text-muted-foreground text-xs">
          Bulletins inclus dans l&apos;OD : {debug.payslips_included}
          {debug.ecritures_lines !== undefined ? ` · ${debug.ecritures_lines} lignes` : ""}
        </p>
      ) : null}
      <ComponentList title="Débits par poste" items={debug.debit_by_component} />
      <ComponentList title="Crédits par poste" items={debug.credit_by_component} />
      {debug.gap_analysis?.salary_equation ? (
        <div>
          <p className="text-muted-foreground text-xs font-medium">Équation salaire</p>
          <p className="text-muted-foreground mt-0.5 text-xs">
            {debug.gap_analysis.salary_equation.formula}
          </p>
          {debug.gap_analysis.salary_equation.note_acomptes ? (
            <p className="text-muted-foreground mt-0.5 text-xs italic">
              {debug.gap_analysis.salary_equation.note_acomptes}
            </p>
          ) : null}
          <ul className="mt-1 space-y-0.5 font-mono text-xs">
            <li className="flex justify-between gap-2">
              <span>Brut bulletins</span>
              <span>{formatEuro(debug.gap_analysis.salary_equation.brut_bulletins)}</span>
            </li>
            <li className="flex justify-between gap-2">
              <span>Cot. salariales bulletins</span>
              <span>
                {formatEuro(debug.gap_analysis.salary_equation.cotisations_salariales_bulletins)}
              </span>
            </li>
            <li className="flex justify-between gap-2">
              <span>PAS bulletins</span>
              <span>{formatEuro(debug.gap_analysis.salary_equation.pas_bulletins)}</span>
            </li>
            <li className="flex justify-between gap-2">
              <span>Crédits attendus (côté salaire)</span>
              <span>
                {formatEuro(debug.gap_analysis.salary_equation.credits_attendus_cote_salaire)}
              </span>
            </li>
            <li className="text-destructive flex justify-between gap-2 font-medium">
              <span>Résidu équation</span>
              <span>{formatEuro(debug.gap_analysis.salary_equation.residu_equation)}</span>
            </li>
          </ul>
        </div>
      ) : null}
      {debug.gap_analysis?.likely_causes && debug.gap_analysis.likely_causes.length > 0 ? (
        <div>
          <p className="text-muted-foreground text-xs font-medium">Causes probables</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs">
            {debug.gap_analysis.likely_causes.map((cause) => (
              <li key={cause.code ?? cause.label}>
                {cause.label}
                {cause.montant !== undefined ? ` (${formatEuro(cause.montant)})` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {debug.gap_analysis?.payslips_breakdown &&
      debug.gap_analysis.payslips_breakdown.length > 0 ? (
        <div>
          <p className="text-muted-foreground text-xs font-medium">Détail par bulletin</p>
          <ul className="mt-1 space-y-1 text-xs">
            {debug.gap_analysis.payslips_breakdown.map((row) => (
              <li key={row.employee_name} className="rounded border px-2 py-1">
                <p className="font-medium">{row.employee_name || "—"}</p>
                <p className="text-muted-foreground font-mono">
                  brut {formatEuro(row.brut)} · net {formatEuro(row.net_a_payer)} · cot.{" "}
                  {formatEuro(row.cotisations_salariales)} · PAS {formatEuro(row.pas)}
                  {row.lignes_cotisations !== undefined
                    ? ` · ${row.lignes_cotisations} lignes cot.`
                    : ""}
                </p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {debug.reconciliation ? (
        <div>
          <p className="text-muted-foreground text-xs font-medium">Rapprochement charges</p>
          <ul className="mt-1 space-y-0.5 font-mono text-xs">
            {Object.entries(debug.reconciliation).map(([key, value]) => (
              <li key={key} className="flex justify-between gap-2">
                <span>{key}</span>
                <span>{formatEuro(value)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {debug.skipped_entries && debug.skipped_entries.length > 0 ? (
        <div>
          <p className="text-muted-foreground text-xs font-medium">Écritures non générées</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs">
            {debug.skipped_entries.map((entry) => (
              <li key={entry}>{entry}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <Button
        type="button"
        size="sm"
        variant="secondary"
        className="h-7 w-full text-xs"
        onClick={() => void handleCopy()}
      >
        {copied ? (
          <>
            <Check className="mr-1.5 h-3 w-3" />
            Copié
          </>
        ) : (
          <>
            <Copy className="mr-1.5 h-3 w-3" />
            Copier le rapport JSON
          </>
        )}
      </Button>
    </div>
  );
}

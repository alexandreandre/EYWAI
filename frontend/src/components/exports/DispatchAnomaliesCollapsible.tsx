import { ChevronDown } from "lucide-react";
import { Link } from "react-router-dom";
import type { DispatchBlockingAnomaly, DispatchChannel } from "@/api/exports";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { OdBalanceDebugPanel } from "@/components/exports/OdBalanceDebugPanel";
import { cn } from "@/lib/utils";

interface DispatchAnomaliesCollapsibleProps {
  channel: DispatchChannel;
  anomalies: DispatchBlockingAnomaly[];
  anomaliesCount: number;
  canGenerate: boolean;
}

export function DispatchAnomaliesCollapsible({
  channel,
  anomalies,
  anomaliesCount,
  canGenerate,
}: DispatchAnomaliesCollapsibleProps) {
  if (canGenerate || anomalies.length === 0) {
    return null;
  }

  const count = anomaliesCount || anomalies.length;
  const channelLabel = channel === "compta" ? "comptabilité" : "banque";

  return (
    <Collapsible className="rounded-md border border-destructive/30 bg-destructive/5">
      <CollapsibleTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          className="group text-destructive h-auto w-full justify-between gap-2 px-3 py-2 text-left text-xs font-normal hover:bg-destructive/10"
        >
          <span>
            {count} blocage{count > 1 ? "s" : ""} empêche{count > 1 ? "nt" : ""} l&apos;envoi{" "}
            {channelLabel}
          </span>
          <ChevronDown className="h-4 w-4 shrink-0 transition-transform group-data-[state=open]:rotate-180" />
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-3 border-t border-destructive/20 px-3 py-3">
        {anomalies.map((anomaly, index) => (
          <div
            key={`${anomaly.source_key}-${anomaly.employee_id ?? "x"}-${index}`}
            className={cn(index > 0 && "border-t border-destructive/15 pt-3")}
          >
            <p className="text-foreground text-xs font-medium">{anomaly.source_label}</p>
            <p className="text-destructive mt-0.5 text-xs">{anomaly.message}</p>
            {anomaly.context_note ? (
              <p className="text-muted-foreground mt-1.5 text-xs leading-relaxed">
                {anomaly.context_note}
              </p>
            ) : null}
            {anomaly.balance_debug ? (
              <OdBalanceDebugPanel debug={anomaly.balance_debug} />
            ) : null}
            {anomaly.action_label && anomaly.action_path ? (
              <Button
                asChild
                size="sm"
                variant="outline"
                className="mt-2 h-8 text-xs"
              >
                <Link to={anomaly.action_path}>{anomaly.action_label}</Link>
              </Button>
            ) : null}
          </div>
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}

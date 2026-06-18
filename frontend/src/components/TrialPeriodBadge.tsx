import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export type TrialPeriodStatus =
  | "in_progress"
  | "ending_soon"
  | "ended"
  | "confirmed"
  | "to_complete";

export interface TrialPeriodData {
  trial_period_applicable?: boolean | null;
  trial_period_status?: TrialPeriodStatus | null;
  trial_period_end_date?: string | null;
  trial_period_days_remaining?: number | null;
  trial_period_renewal_possible?: boolean | null;
}

interface TrialPeriodBadgeProps {
  data: TrialPeriodData | null | undefined;
  className?: string;
}

function formatDateFR(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    return new Date(iso.slice(0, 10)).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return null;
  }
}

function getStatusConfig(status: TrialPeriodStatus | null | undefined): {
  label: string;
  className: string;
} {
  switch (status) {
    case "in_progress":
      return {
        label: "En cours",
        className: "bg-blue-100 text-blue-800 border-blue-200",
      };
    case "ending_soon":
      return {
        label: "Fin proche",
        className: "bg-orange-100 text-orange-800 border-orange-200",
      };
    case "ended":
      return {
        label: "Terminée",
        className: "bg-red-100 text-red-700 border-red-200",
      };
    case "confirmed":
      return {
        label: "Confirmée",
        className: "bg-green-100 text-green-800 border-green-200",
      };
    case "to_complete":
      return {
        label: "À renseigner",
        className: "bg-gray-100 text-gray-700 border-gray-200",
      };
    default:
      return {
        label: "À renseigner",
        className: "bg-gray-100 text-gray-700 border-gray-200",
      };
  }
}

function getTooltipMessage(data: TrialPeriodData): string | null {
  const status = data.trial_period_status;
  const endLabel = formatDateFR(data.trial_period_end_date);
  const days = data.trial_period_days_remaining;

  if (status === "confirmed") {
    return endLabel ? `Embauche confirmée (essai jusqu'au ${endLabel})` : "Embauche confirmée";
  }
  if (status === "to_complete") {
    return "Renseignez la durée ; la fin sera calculée à partir de la date d'entrée.";
  }
  if (endLabel && days != null) {
    if (days < 0) return `Période d'essai terminée le ${endLabel}`;
    if (days === 0) return `Se termine aujourd'hui (${endLabel})`;
    return `Fin le ${endLabel} — J-${days}`;
  }
  if (endLabel) return `Fin le ${endLabel}`;
  return null;
}

export function TrialPeriodBadge({ data, className }: TrialPeriodBadgeProps) {
  if (!data?.trial_period_applicable || !data.trial_period_status) {
    return null;
  }

  const { label, className: statusClassName } = getStatusConfig(data.trial_period_status);
  const tooltipMessage = getTooltipMessage(data);

  const badge = (
    <Badge variant="outline" className={cn(statusClassName, tooltipMessage && "cursor-help")}>
      {label}
    </Badge>
  );

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <span className="text-sm text-muted-foreground">Période d&apos;essai :</span>
      {tooltipMessage ? (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>{badge}</TooltipTrigger>
            <TooltipContent>
              <p>{tooltipMessage}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      ) : (
        badge
      )}
    </div>
  );
}

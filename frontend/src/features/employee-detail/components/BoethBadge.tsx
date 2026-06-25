import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { EmployeeBoethProfile } from '@/api/oethSettings';

interface BoethBadgeProps {
  profile: EmployeeBoethProfile | null | undefined;
  className?: string;
}

function formatDateFR(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    return new Date(iso.slice(0, 10)).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  } catch {
    return null;
  }
}

function shortBoethLabel(profile: EmployeeBoethProfile): string {
  const label = profile.boeth_label ?? profile.boeth_code;
  const dash = label.indexOf(' — ');
  if (dash > 0) {
    return label.slice(0, dash).trim();
  }
  return label;
}

function daysUntil(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const target = new Date(iso.slice(0, 10));
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  target.setHours(0, 0, 0, 0);
  return Math.ceil((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

function getAlertState(profile: EmployeeBoethProfile): {
  className: string;
  tooltipExtra: string | null;
} {
  const validToDays = daysUntil(profile.valid_to);
  const docDays = daysUntil(profile.document_expires_at);

  if (validToDays != null && validToDays < 0) {
    return {
      className: 'bg-red-100 text-red-700 border-red-200',
      tooltipExtra: `Validité expirée le ${formatDateFR(profile.valid_to)}`,
    };
  }
  if (docDays != null && docDays < 0) {
    return {
      className: 'bg-red-100 text-red-700 border-red-200',
      tooltipExtra: `Justificatif expiré le ${formatDateFR(profile.document_expires_at)}`,
    };
  }
  if (validToDays != null && validToDays <= 60) {
    return {
      className: 'bg-orange-100 text-orange-800 border-orange-200',
      tooltipExtra: `Validité jusqu'au ${formatDateFR(profile.valid_to)}`,
    };
  }
  if (docDays != null && docDays <= 60) {
    return {
      className: 'bg-orange-100 text-orange-800 border-orange-200',
      tooltipExtra: `Justificatif expire le ${formatDateFR(profile.document_expires_at)}`,
    };
  }
  return {
    className: 'bg-sky-100 text-sky-800 border-sky-200',
    tooltipExtra: null,
  };
}

function buildTooltip(profile: EmployeeBoethProfile): string {
  const parts = [
    profile.boeth_label ?? `Code ${profile.boeth_code}`,
    `Valide depuis le ${formatDateFR(profile.valid_from) ?? profile.valid_from}`,
  ];
  if (profile.valid_to) {
    parts.push(`Jusqu'au ${formatDateFR(profile.valid_to)}`);
  }
  const { tooltipExtra } = getAlertState(profile);
  if (tooltipExtra) {
    parts.push(tooltipExtra);
  }
  return parts.join(' · ');
}

export function BoethBadge({ profile, className }: BoethBadgeProps) {
  if (!profile?.boeth_code) {
    return null;
  }

  const shortLabel = shortBoethLabel(profile);
  const { className: statusClassName } = getAlertState(profile);
  const tooltipMessage = buildTooltip(profile);

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <span className="text-sm text-muted-foreground">BOETH :</span>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge
              variant="outline"
              className={cn(statusClassName, 'cursor-help font-normal')}
            >
              {shortLabel}
            </Badge>
          </TooltipTrigger>
          <TooltipContent>
            <p>{tooltipMessage}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
}

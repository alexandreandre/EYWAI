import { AlertTriangle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

export type ConflictBadgeType = 'absence' | 'overlap' | 'overtime' | 'rest';

export interface ConflictBadgeProps {
  type: ConflictBadgeType;
  message: string;
}

const TYPE_STYLES: Record<
  ConflictBadgeType,
  { badge: string; label: string }
> = {
  absence: {
    badge: 'border-red-600 bg-red-600 text-white hover:bg-red-600',
    label: 'Absence',
  },
  overlap: {
    badge: 'border-red-600 bg-red-600 text-white hover:bg-red-600',
    label: 'Chevauchement',
  },
  overtime: {
    badge: 'border-orange-500 bg-orange-500 text-white hover:bg-orange-500',
    label: 'Heures',
  },
  rest: {
    badge: 'border-amber-400 bg-amber-400 text-amber-950 hover:bg-amber-400',
    label: 'Repos',
  },
};

export function ConflictBadge({ type, message }: ConflictBadgeProps) {
  const cfg = TYPE_STYLES[type];
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className="inline-flex shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          aria-label={message}
        >
          <Badge
            variant="outline"
            className={cn('h-5 gap-0.5 px-1.5 text-[10px] font-semibold', cfg.badge)}
          >
            <AlertTriangle className="h-3 w-3" aria-hidden />
            {cfg.label}
          </Badge>
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs text-left">
        <p className="text-xs">{message}</p>
      </TooltipContent>
    </Tooltip>
  );
}

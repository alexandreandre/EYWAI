import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

type RatesVersionBadgeProps = {
  version: number | null | undefined;
  comment: string | null;
};

/** Badge version avec infobulle (compatible TooltipTrigger + ref). */
export function RatesVersionBadge({ version, comment }: RatesVersionBadgeProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex cursor-default">
          <Badge variant="outline" className="shrink-0">
            v{version ?? '?'}
          </Badge>
        </span>
      </TooltipTrigger>
      <TooltipContent>
        <p>{comment || 'Version de la configuration'}</p>
      </TooltipContent>
    </Tooltip>
  );
}

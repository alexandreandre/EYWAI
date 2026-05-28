import { useEffect, useState, type ReactNode } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

import type { RateCategory } from '@/api/rates';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { TooltipProvider } from '@/components/ui/tooltip';
import { RatesVersionBadge } from '@/components/rates/RatesVersionBadge';
import { RatesUpdateButton } from '@/components/rates/RatesUpdateButton';
import { formatRateDate, getRateDateColor } from '@/lib/ratesUtils';
import { RatesSourceLinks } from '@/components/rates/RatesSourceLinks';
import { cn } from '@/lib/utils';

type RatesCategoryCardProps = {
  title: string;
  category: RateCategory;
  children: ReactNode;
  highlight?: boolean;
  onUpdate?: () => void;
  isUpdating?: boolean;
  canUpdate?: boolean;
  defaultOpen?: boolean;
};

export function RatesCategoryCard({
  title,
  category,
  children,
  highlight,
  onUpdate,
  isUpdating,
  canUpdate = true,
  defaultOpen = false,
}: RatesCategoryCardProps) {
  const [open, setOpen] = useState(defaultOpen || Boolean(highlight));

  useEffect(() => {
    if (highlight) setOpen(true);
  }, [highlight]);

  return (
    <Card
      className={cn(
        'shadow-sm flex flex-col',
        highlight && 'ring-2 ring-primary/40 ring-offset-2',
      )}
    >
      <Collapsible open={open} onOpenChange={setOpen}>
        <CardHeader className="flex-row items-start justify-between space-y-0 pb-2 gap-2">
          <CollapsibleTrigger asChild>
            <Button
              variant="ghost"
              className="h-auto min-w-0 flex-1 justify-start gap-2 px-0 py-0 text-foreground hover:bg-transparent hover:text-foreground"
            >
              {open ? (
                <ChevronDown className="h-4 w-4 shrink-0" />
              ) : (
                <ChevronRight className="h-4 w-4 shrink-0" />
              )}
              <span className="text-left text-lg font-semibold">{title}</span>
            </Button>
          </CollapsibleTrigger>
          <div className="flex items-center gap-2 shrink-0">
            {canUpdate && onUpdate && (
              <RatesUpdateButton
                label="Mettre à jour"
                onClick={onUpdate}
                isRunning={isUpdating}
              />
            )}
            <TooltipProvider>
              <RatesVersionBadge version={category.version} comment={category.comment} />
            </TooltipProvider>
          </div>
        </CardHeader>
        <CollapsibleContent>
          <CardContent className="flex-grow pt-0">
            {children}
            <RatesSourceLinks links={category.source_links} />
            <p
              className={`text-xs mt-4 text-right font-medium ${getRateDateColor(category.last_checked_at)}`}
            >
              Contrôlé le : {formatRateDate(category.last_checked_at)}
            </p>
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}

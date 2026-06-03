import { useEffect, useState, type ReactNode } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

import type { RateCategory } from '@/api/rates';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { RatesSingleUpdateMenu } from '@/components/rates/RatesActionsMenu';
import {
  RatesPanelFooter,
  RatesPanelHeader,
  RatesPanelShell,
} from '@/components/rates/RatesPanelShell';

type RatesCategoryCardProps = {
  title: string;
  rateKey: string;
  category: RateCategory;
  sourceLinks?: string[] | null;
  children: ReactNode;
  highlight?: boolean;
  onUpdate?: () => void;
  isUpdating?: boolean;
  canUpdate?: boolean;
  disabled?: boolean;
  defaultOpen?: boolean;
};

export function RatesCategoryCard({
  title,
  rateKey,
  category,
  sourceLinks,
  children,
  highlight,
  onUpdate,
  isUpdating,
  canUpdate = true,
  disabled,
  defaultOpen = false,
}: RatesCategoryCardProps) {
  const [open, setOpen] = useState(defaultOpen || Boolean(highlight));

  useEffect(() => {
    if (highlight) setOpen(true);
  }, [highlight]);

  return (
    <RatesPanelShell highlight={highlight}>
      <Collapsible open={open} onOpenChange={setOpen}>
        <RatesPanelHeader
          lastCheckedAt={category.last_checked_at}
          trigger={
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                className="h-auto min-w-0 flex-1 justify-start gap-2 px-0 py-0 font-semibold text-foreground hover:bg-transparent hover:text-foreground"
              >
                {open ? (
                  <ChevronDown className="h-4 w-4 shrink-0" />
                ) : (
                  <ChevronRight className="h-4 w-4 shrink-0" />
                )}
                <span className="min-w-0 flex-1 text-left text-base leading-snug">{title}</span>
              </Button>
            </CollapsibleTrigger>
          }
          actions={
            canUpdate && onUpdate ? (
              <RatesSingleUpdateMenu
                onUpdate={onUpdate}
                isRunning={isUpdating}
                disabled={disabled}
                compact
                className="-mr-1 shrink-0"
              />
            ) : null
          }
        />
        <CollapsibleContent>
          <div className="px-4 pb-3">{children}</div>
          <RatesPanelFooter category={category} links={sourceLinks} />
        </CollapsibleContent>
      </Collapsible>
    </RatesPanelShell>
  );
}

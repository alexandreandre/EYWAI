import type { ReactNode } from 'react';

import type { RateCategory } from '@/api/rates';
import { RatesLastCheckedMeta } from '@/components/rates/RatesLastCheckedMeta';
import { RatesSourceLinks } from '@/components/rates/RatesSourceLinks';
import { cn } from '@/lib/utils';

export function ratesPanelSurfaceClass(highlight?: boolean) {
  return cn(
    'flex flex-col overflow-hidden rounded-lg border border-border/80 bg-card transition-colors',
    highlight && 'border-foreground/25',
    !highlight && 'hover:border-border',
  );
}

type RatesPanelShellProps = {
  children: ReactNode;
  highlight?: boolean;
  className?: string;
};

export function RatesPanelShell({ children, highlight, className }: RatesPanelShellProps) {
  return <div className={cn(ratesPanelSurfaceClass(highlight), className)}>{children}</div>;
}

type RatesPanelHeaderProps = {
  title?: ReactNode;
  lastCheckedAt?: string | null;
  actions?: ReactNode;
  trigger?: ReactNode;
  className?: string;
};

export function RatesPanelHeader({
  title,
  lastCheckedAt,
  actions,
  trigger,
  className,
}: RatesPanelHeaderProps) {
  return (
    <div
      className={cn(
        'flex min-h-[4rem] flex-col gap-1.5 border-b border-border/60 px-4 py-3',
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-1 items-start gap-1">
          {trigger ?? (title ? <div className="min-w-0 font-semibold leading-snug">{title}</div> : null)}
        </div>
        {actions}
      </div>
      {lastCheckedAt !== undefined && (
        <RatesLastCheckedMeta lastCheckedAt={lastCheckedAt} />
      )}
    </div>
  );
}

type RatesPanelFooterProps = {
  category?: RateCategory;
  /** URLs explicites ; sinon repli sur category.source_links */
  links?: string[] | null;
  className?: string;
};

export function RatesPanelFooter({ category, links, className }: RatesPanelFooterProps) {
  const resolved = links ?? category?.source_links ?? null;
  return (
    <div className={cn('border-t border-border/60 px-4 py-3', className)}>
      <RatesSourceLinks links={resolved} variant="pill" />
    </div>
  );
}

import type { KeyboardEvent, ReactNode } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

import { cn } from '@/lib/utils';

type RatesSectionHeaderProps = {
  open: boolean;
  title: string;
  description?: string;
  actions?: ReactNode;
  onToggle: () => void;
  badge?: ReactNode;
};

function stopActionToggle(event: { stopPropagation: () => void }) {
  event.stopPropagation();
}

export function RatesSectionHeader({
  open,
  title,
  description,
  actions,
  onToggle,
  badge,
}: RatesSectionHeaderProps) {
  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onToggle();
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-expanded={open}
      onClick={onToggle}
      onKeyDown={handleKeyDown}
      className={cn(
        'mb-4 flex cursor-pointer items-end justify-between gap-3 rounded-md border-b border-border/70 pb-3',
        'transition-colors hover:bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
      )}
    >
      <div className="flex min-w-0 flex-1 items-start gap-2 py-1.5 pl-0.5">
        {open ? (
          <ChevronDown className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
        ) : (
          <ChevronRight className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
        )}
        <span className="min-w-0 text-left">
          <span className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold tracking-tight text-foreground">{title}</h2>
            {badge}
          </span>
          {description ? (
            <span className="mt-0.5 block text-sm font-normal text-muted-foreground">
              {description}
            </span>
          ) : null}
        </span>
      </div>
      {actions ? (
        <div
          className="flex shrink-0 flex-wrap items-center gap-2 py-1"
          onClick={stopActionToggle}
          onKeyDown={stopActionToggle}
          onPointerDown={stopActionToggle}
        >
          {actions}
        </div>
      ) : null}
    </div>
  );
}

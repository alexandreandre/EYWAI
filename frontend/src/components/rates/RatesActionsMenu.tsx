import type { SyntheticEvent } from 'react';
import { Loader2, MoreVertical, RefreshCw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

export type RatesActionMenuItem = {
  id: string;
  label: string;
  onSelect: () => void;
  disabled?: boolean;
  isRunning?: boolean;
};

type RatesActionsMenuProps = {
  items: RatesActionMenuItem[];
  align?: 'start' | 'end';
  className?: string;
  /** Style discret pour en-têtes d’accordéon et lignes compactes */
  compact?: boolean;
};

function stopTriggerPropagation(event: SyntheticEvent) {
  event.stopPropagation();
}

export function RatesActionsMenu({
  items,
  align = 'end',
  className,
  compact = false,
}: RatesActionsMenuProps) {
  if (items.length === 0) return null;

  const anyRunning = items.some((item) => item.isRunning);
  const triggerDisabled = items.every((item) => item.disabled || item.isRunning);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className={cn(
            'shrink-0',
            compact
              ? 'h-8 w-8 text-muted-foreground hover:bg-muted/60 hover:text-foreground'
              : 'h-9 w-9 text-muted-foreground hover:bg-muted/60 hover:text-foreground',
            className,
          )}
          disabled={triggerDisabled}
          onPointerDown={stopTriggerPropagation}
          onClick={stopTriggerPropagation}
        >
          {anyRunning ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <MoreVertical className="h-4 w-4" aria-hidden />
          )}
          <span className="sr-only">Actions</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align={align}
        className="w-52"
        onClick={stopTriggerPropagation}
        onPointerDown={stopTriggerPropagation}
      >
        {items.map((item) => (
          <DropdownMenuItem
            key={item.id}
            disabled={item.disabled || item.isRunning}
            onSelect={() => item.onSelect()}
          >
            {item.isRunning ? (
              <Loader2 className="mr-2 h-4 w-4 shrink-0 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4 shrink-0" />
            )}
            <span className="truncate">{item.label}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

type RatesSingleUpdateMenuProps = Omit<RatesActionsMenuProps, 'items'> & {
  onUpdate: () => void;
  isRunning?: boolean;
  disabled?: boolean;
  label?: string;
};

export function RatesSingleUpdateMenu({
  onUpdate,
  isRunning,
  disabled,
  label = 'Mise à jour',
  ...menuProps
}: RatesSingleUpdateMenuProps) {
  return (
    <RatesActionsMenu
      items={[
        {
          id: 'update',
          label,
          onSelect: onUpdate,
          isRunning,
          disabled,
        },
      ]}
      {...menuProps}
    />
  );
}

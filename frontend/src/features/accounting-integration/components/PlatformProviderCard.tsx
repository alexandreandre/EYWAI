import { useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import { ProviderLogo } from '@/components/integrations/ProviderLogo';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';

type PlatformProviderCardProps = {
  providerKey: string;
  name: string;
  description: string;
  enabled: boolean;
  connectorReady: boolean;
  hasPlatformCredentials: boolean;
  toggleDisabled?: boolean;
  onEnabledChange: (enabled: boolean) => void;
  children?: ReactNode;
  footer?: ReactNode;
  defaultOpen?: boolean;
};

export function PlatformProviderCard({
  providerKey,
  name,
  description,
  enabled,
  connectorReady,
  hasPlatformCredentials,
  toggleDisabled,
  onEnabledChange,
  children,
  footer,
  defaultOpen = false,
}: PlatformProviderCardProps) {
  const [open, setOpen] = useState(defaultOpen);
  const hasDetails = Boolean(children || footer);

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className={cn(
        'flex w-full flex-col self-start rounded-lg border bg-card transition-colors',
        open && 'ring-1 ring-primary/20',
      )}
    >
      <div className="flex min-h-[5.5rem] shrink-0 flex-col justify-center gap-2 p-4">
        <div className="flex items-start gap-2">
          {hasDetails ? (
            <CollapsibleTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="mt-0.5 h-7 w-7 shrink-0"
                aria-label={open ? 'Replier la carte' : 'Déplier la carte'}
              >
                <ChevronDown
                  className={cn(
                    'h-4 w-4 transition-transform duration-200',
                    !open && '-rotate-90',
                  )}
                />
              </Button>
            </CollapsibleTrigger>
          ) : (
            <span className="w-7 shrink-0" aria-hidden />
          )}

          <ProviderLogo providerKey={providerKey} size="lg" className="shrink-0" />

          <button
            type="button"
            className={cn(
              'min-w-0 flex-1 text-left',
              hasDetails && 'cursor-pointer',
            )}
            onClick={hasDetails ? () => setOpen((v) => !v) : undefined}
          >
            <p className="font-medium leading-tight">{name}</p>
            <p className="text-muted-foreground mt-0.5 line-clamp-2 text-xs leading-relaxed">
              {description}
            </p>
          </button>

          <Switch
            checked={enabled}
            disabled={toggleDisabled}
            onCheckedChange={onEnabledChange}
            className="shrink-0"
            aria-label={`Activer ${name}`}
          />
        </div>

        <div className="flex flex-wrap gap-2 pl-9">
          {connectorReady ? (
            <Badge>Connecteur prêt</Badge>
          ) : (
            <Badge variant="outline">Bientôt</Badge>
          )}
          {hasPlatformCredentials ? (
            <Badge variant="secondary">Credentials plateforme</Badge>
          ) : null}
          {enabled ? <Badge variant="secondary">Activé</Badge> : null}
        </div>
      </div>

      {hasDetails ? (
        <CollapsibleContent>
          <div className="space-y-3 border-t px-4 pb-4 pt-3">{children}</div>
          {footer ? (
            <p className="text-muted-foreground border-t px-4 py-2 text-xs">{footer}</p>
          ) : null}
        </CollapsibleContent>
      ) : null}
    </Collapsible>
  );
}

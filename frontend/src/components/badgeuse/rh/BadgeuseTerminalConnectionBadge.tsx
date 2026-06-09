import { cn } from '@/lib/utils';
import type { BadgeuseTerminalAuthMode } from '@/hooks/useBadgeuseTerminalAuth';

type Props = {
  mode: BadgeuseTerminalAuthMode;
  label?: string;
  className?: string;
};

export function BadgeuseTerminalConnectionBadge({ mode, label, className }: Props) {
  const connected = mode === 'terminal' || mode === 'rh';
  const modeLabel =
    mode === 'terminal'
      ? `Terminal${label ? ` · ${label}` : ''}`
      : mode === 'rh'
        ? 'Session RH'
        : 'Hors ligne';

  return (
    <div
      className={cn(
        'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium',
        connected
          ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
          : 'border-amber-200 bg-amber-50 text-amber-900',
        className
      )}
      title={connected ? 'Connexion active' : 'Session expirée'}
    >
      <span
        className={cn(
          'h-2 w-2 rounded-full',
          connected ? 'bg-emerald-500' : 'bg-amber-500'
        )}
        aria-hidden
      />
      {connected ? 'Connecté' : 'Session expirée'} · {modeLabel}
    </div>
  );
}

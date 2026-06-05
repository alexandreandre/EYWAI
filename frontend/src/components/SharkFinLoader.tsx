import { SharkFinBootProgress } from '@/components/SharkFinBootProgress';
import { cn } from '@/lib/utils';

type SharkFinLoaderProps = {
  /** Libellé affiché sous l'aileron. */
  label?: string;
  /** Plein écran centré (min-h-[50vh]) ou section inline. */
  variant?: 'fullPage' | 'section' | 'compact';
  className?: string;
};

/**
 * Indicateur de chargement indéterminé : aileron de gauche à droite sur la ligne d'eau.
 * À utiliser pour les écrans / sections / onglets (pas les boutons d'action).
 */
export function SharkFinLoader({
  label = 'Chargement…',
  variant = 'section',
  className,
}: SharkFinLoaderProps) {
  const isCompact = variant === 'compact';

  return (
    <div
      className={cn(
        'flex w-full flex-col items-center justify-center',
        isCompact ? 'gap-1' : 'gap-3',
        variant === 'fullPage' && 'min-h-[50vh]',
        className,
      )}
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label={label}
    >
      <div className={cn('w-full px-4', isCompact ? 'max-w-[140px]' : 'max-w-xs')}>
        <SharkFinBootProgress className={isCompact ? 'pt-4 pb-1' : 'pt-6 pb-2'} />
      </div>
      {label && !isCompact ? (
        <p className="text-center text-sm text-muted-foreground">{label}</p>
      ) : null}
    </div>
  );
}

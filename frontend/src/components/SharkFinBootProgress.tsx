import { cn } from '@/lib/utils';

type SharkFinBootProgressProps = {
  /** Conservé pour l'accessibilité ; la barre n'affiche pas d'avancement. */
  value?: number;
  className?: string;
};

/**
 * Aileron dorsal : base plate posée sur la ligne d'eau, dos concave penché
 * vers l'arrière, pointe vers l'avant (droite).
 */
function SharkFin({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 38 28"
      width={38}
      height={28}
      className={cn('text-primary', className)}
      aria-hidden
    >
      <path d="M5 28 Q 18 25 26 5 Q 30 13 33 28 Z" fill="currentColor" />
    </svg>
  );
}

/**
 * Écran de démarrage : un aileron de requin avance en continu de gauche à
 * droite sur une ligne d'eau fixe (la barre n'affiche pas de pourcentage).
 */
export function SharkFinBootProgress({ value, className }: SharkFinBootProgressProps) {
  const progress =
    typeof value === 'number' ? Math.min(100, Math.max(0, value)) : undefined;

  return (
    <div
      className={cn('relative w-full pt-8', className)}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={progress !== undefined ? Math.round(progress) : undefined}
    >
      {/* Ligne d'eau fixe */}
      <div className="h-2 w-full rounded-full bg-sky-100 dark:bg-sky-950/50" />

      {/* Aileron : sa base plate repose sur la ligne d'eau (top de la barre) */}
      <div className="pointer-events-none absolute inset-x-0 bottom-2">
        <div className="shark-swimmer absolute bottom-0 left-0">
          <div className="shark-surger origin-bottom -translate-x-1/2">
            <SharkFin className="block drop-shadow-[0_1px_1px_rgba(0,0,0,0.12)]" />
          </div>
        </div>
      </div>
    </div>
  );
}

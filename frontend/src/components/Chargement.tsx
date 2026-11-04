import { BarreDeProgression } from '@/components/BarreDeProgression';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { texteDuChargement, type ProgressionConnue } from '@/components/chargementTexte';

type ChargementProps = {
  /**
   * Ce qui charge, en mots (« Chargement des bulletins… »). Vide : des lignes
   * grisées tiennent la place du contenu qui arrive.
   */
  label?: string;
  /**
   * fullPage : centré sur au moins la moitié de l'écran ; section : centré dans
   * la zone ; compact : petit, pour une carte ou un encart ; lignes : des lignes
   * grisées à la place du contenu.
   */
  variant?: 'fullPage' | 'section' | 'compact' | 'lignes';
  /** Avancement connu : « Calcul des bulletins : 12 sur 42 ». */
  progression?: ProgressionConnue | null;
  className?: string;
};

const TEXTE_PAR_DEFAUT = 'Chargement…';

/**
 * Ce qui charge, dit en mots sous une barre fine ; ou des lignes grisées à la
 * place du contenu qui arrive. Pour les écrans, sections et onglets (pas les
 * boutons d'action, qui gardent leur propre indicateur).
 */
export function Chargement({
  label = TEXTE_PAR_DEFAUT,
  variant = 'section',
  progression = null,
  className,
}: ChargementProps) {
  const texte = texteDuChargement(label, progression);

  if (variant === 'lignes' || !label.trim()) {
    return (
      <div
        className={cn('w-full space-y-2', className)}
        role="status"
        aria-live="polite"
        aria-busy="true"
      >
        <Skeleton className="h-3 w-3/4 motion-reduce:animate-none" />
        <Skeleton className="h-3 w-1/2 motion-reduce:animate-none" />
        <span className="sr-only">{texte || TEXTE_PAR_DEFAUT}</span>
      </div>
    );
  }

  const compact = variant === 'compact';
  const pourcentage =
    progression && progression.total > 0 ? (progression.faits / progression.total) * 100 : null;

  return (
    <div
      className={cn(
        'flex w-full flex-col items-center justify-center',
        compact ? 'gap-1.5' : 'gap-3',
        variant === 'fullPage' && 'min-h-[50vh]',
        variant === 'section' && 'py-6',
        className,
      )}
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <BarreDeProgression
        valeur={pourcentage}
        className={compact ? 'max-w-[160px]' : 'max-w-xs'}
      />
      <p
        className={cn(
          'text-center text-muted-foreground',
          compact ? 'text-xs' : 'text-sm',
          progression && 'tabular-nums',
        )}
      >
        {texte}
      </p>
    </div>
  );
}

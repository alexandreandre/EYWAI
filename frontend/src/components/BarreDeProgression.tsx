import { cn } from '@/lib/utils';

type BarreDeProgressionProps = {
  /** Avancement connu, de 0 à 100. Absent : la barre dit seulement que ça avance. */
  valeur?: number | null;
  /** Ce que mesure la barre, pour les lecteurs d'écran. */
  libelle?: string;
  className?: string;
};

/**
 * Barre fine d'avancement. Avancement connu : elle se remplit. Inconnu : un
 * segment la parcourt (immobile si l'utilisatrice a demandé moins d'animations).
 * Le texte de ce qui se passe s'écrit à côté, en mots : la barre ne le remplace pas.
 */
export function BarreDeProgression({ valeur, libelle, className }: BarreDeProgressionProps) {
  const pourcentage =
    typeof valeur === 'number' && Number.isFinite(valeur)
      ? Math.min(100, Math.max(0, valeur))
      : null;

  return (
    <div
      className={cn('h-1 w-full overflow-hidden rounded-full bg-primary/15', className)}
      role="progressbar"
      aria-label={libelle || undefined}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pourcentage !== null ? Math.round(pourcentage) : undefined}
    >
      {pourcentage !== null ? (
        <div
          className="h-full rounded-full bg-primary motion-safe:transition-[width] motion-safe:duration-300 motion-safe:ease-out"
          style={{ width: `${pourcentage}%` }}
        />
      ) : (
        <div className="chargement-segment h-full w-1/3 rounded-full bg-primary/70" />
      )}
    </div>
  );
}

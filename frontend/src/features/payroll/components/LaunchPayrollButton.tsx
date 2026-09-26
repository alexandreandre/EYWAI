import { Link } from 'react-router-dom';
import { RefreshCw, Rocket } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useCanLaunchPayroll } from '@/features/payroll/hooks/useCanLaunchPayroll';

interface LaunchPayrollButtonProps {
  className?: string;
  fullWidth?: boolean;
  size?: 'sm' | 'default';
  enabled?: boolean;
  /** Force l’apparence neutre (gris) pendant le chargement du parcours paie. */
  pipelineLoading?: boolean;
}

export function LaunchPayrollButton({
  className,
  fullWidth = false,
  size = 'sm',
  enabled = true,
  pipelineLoading = false,
}: LaunchPayrollButtonProps) {
  const { canLaunchPayroll, isError, retry } = useCanLaunchPayroll(enabled);
  const showAsReady = canLaunchPayroll && !pipelineLoading;

  // Compteurs du parcours illisibles : le verrou ne s'ouvre pas en silence,
  // il le dit et propose de réessayer (constat C1 de l'audit du 25/09).
  if (isError) {
    return (
      <Button
        type="button"
        size={size}
        variant="outline"
        onClick={retry}
        className={cn(
          'gap-2 shadow-sm border-amber-300/70 bg-amber-50 text-amber-900 hover:bg-amber-100 hover:text-amber-900 dark:border-amber-500/40 dark:bg-amber-950/30 dark:text-amber-100 dark:hover:bg-amber-950/50',
          fullWidth && 'w-full',
          className,
        )}
        title="Le parcours de préparation n'a pas pu être vérifié. Cliquez pour réessayer."
        aria-label="Contrôle indisponible : réessayer"
      >
        <RefreshCw className="h-4 w-4 shrink-0" aria-hidden />
        Contrôle indisponible
      </Button>
    );
  }

  return (
    <Button
      size={size}
      disabled={!showAsReady}
      className={cn(
        'gap-2 shadow-sm',
        fullWidth && 'w-full',
        showAsReady
          ? 'bg-success text-success-foreground hover:bg-success/90 ring-1 ring-success/40'
          : 'cursor-not-allowed bg-muted text-muted-foreground hover:bg-muted disabled:opacity-100',
        className,
      )}
      title={
        pipelineLoading
          ? 'Vérification du parcours de préparation…'
          : showAsReady
            ? 'Lancer la paie'
            : 'Terminez les étapes en attente avant de lancer la paie'
      }
      asChild={showAsReady}
    >
      {showAsReady ? (
        <Link to="/payroll/generate">
          <Rocket className="h-4 w-4 shrink-0" />
          Lancer la paie
        </Link>
      ) : (
        <>
          <Rocket className="h-4 w-4 shrink-0 opacity-50" />
          Lancer la paie
        </>
      )}
    </Button>
  );
}

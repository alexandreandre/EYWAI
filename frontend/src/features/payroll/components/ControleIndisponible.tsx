import { AlertTriangle, Loader2, RefreshCw } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';

interface ControleIndisponibleProps {
  titre: string;
  description: string;
  onRetry?: () => void;
  isRetrying?: boolean;
  className?: string;
}

/**
 * Une vérification qui n'a pas pu se faire le dit : se taire ferait croire
 * qu'il n'y a rien à signaler (constat C1 de l'audit du 25/09).
 */
export function ControleIndisponible({
  titre,
  description,
  onRetry,
  isRetrying = false,
  className,
}: ControleIndisponibleProps) {
  return (
    <Alert variant="destructive" className={className}>
      <AlertTriangle className="h-4 w-4" aria-hidden />
      <AlertTitle className="text-sm">{titre}</AlertTitle>
      <AlertDescription className="space-y-2 text-xs">
        <p>{description}</p>
        {onRetry && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-8 gap-2 text-xs"
            onClick={onRetry}
            disabled={isRetrying}
          >
            {isRetrying ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" aria-hidden />
            )}
            Réessayer
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
}

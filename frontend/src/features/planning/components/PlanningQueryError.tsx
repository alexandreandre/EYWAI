import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function PlanningQueryError({
  message,
  onRetry,
  className,
}: {
  message: string;
  onRetry: () => void;
  className?: string;
}) {
  return (
    <div
      className={`rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-center ${className ?? ''}`}
    >
      <p className="text-sm text-destructive">{message}</p>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="mt-3 gap-2"
        onClick={onRetry}
      >
        <RefreshCw className="h-4 w-4" />
        Réessayer
      </Button>
    </div>
  );
}

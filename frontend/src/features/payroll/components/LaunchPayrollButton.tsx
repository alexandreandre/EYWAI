import { Link } from 'react-router-dom';
import { Rocket } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useCanLaunchPayroll } from '@/features/payroll/hooks/useCanLaunchPayroll';

interface LaunchPayrollButtonProps {
  className?: string;
  fullWidth?: boolean;
  size?: 'sm' | 'default';
  enabled?: boolean;
}

export function LaunchPayrollButton({
  className,
  fullWidth = false,
  size = 'sm',
  enabled = true,
}: LaunchPayrollButtonProps) {
  const { canLaunchPayroll } = useCanLaunchPayroll(enabled);

  return (
    <Button
      size={size}
      disabled={!canLaunchPayroll}
      className={cn(
        'gap-2 shadow-sm',
        fullWidth && 'w-full',
        canLaunchPayroll
          ? 'bg-success text-success-foreground hover:bg-success/90 ring-1 ring-success/40'
          : 'cursor-not-allowed bg-muted text-muted-foreground hover:bg-muted disabled:opacity-100',
        className,
      )}
      title={
        canLaunchPayroll
          ? 'Lancer la paie'
          : 'Terminez les étapes en attente avant de lancer la paie'
      }
      asChild={canLaunchPayroll}
    >
      {canLaunchPayroll ? (
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

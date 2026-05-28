import { Loader2, RefreshCw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type RatesUpdateButtonProps = {
  label?: string;
  onClick: () => void;
  disabled?: boolean;
  isRunning?: boolean;
  variant?: 'default' | 'outline' | 'ghost';
  size?: 'default' | 'sm' | 'icon';
  className?: string;
};

export function RatesUpdateButton({
  label = 'Mettre à jour',
  onClick,
  disabled,
  isRunning,
  variant = 'outline',
  size = 'sm',
  className,
}: RatesUpdateButtonProps) {
  return (
    <Button
      type="button"
      variant={variant}
      size={size}
      className={cn('shrink-0', className)}
      onClick={onClick}
      disabled={disabled || isRunning}
    >
      {isRunning ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <RefreshCw className="h-3.5 w-3.5" />
      )}
      {size !== 'icon' && label ? (
        <span className="ml-1.5 max-w-[10rem] truncate">{label}</span>
      ) : null}
    </Button>
  );
}

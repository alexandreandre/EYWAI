import { RhPageHeader } from '@/components/layout';
import { Button } from '@/components/ui/button';
import { Sparkles } from 'lucide-react';
import { LaunchPayrollButton } from '@/features/payroll/components/LaunchPayrollButton';

interface DashboardHeaderProps {
  firstName: string;
  dateLabel: string;
  onCopilotClick: () => void;
}

export function DashboardHeader({
  firstName,
  dateLabel,
  onCopilotClick,
}: DashboardHeaderProps) {
  return (
    <RhPageHeader
      title={`Bonjour ${firstName},`}
      description={dateLabel}
      afterDescription={<p className="text-sm text-muted-foreground">Cockpit de pilotage RH</p>}
      actions={
        <>
          <LaunchPayrollButton />
          <Button
            onClick={onCopilotClick}
            className="border-0 bg-gradient-to-r from-pink-500 via-rose-500 to-fuchsia-500 text-white shadow-md shadow-pink-500/30 hover:from-pink-600 hover:via-rose-600 hover:to-fuchsia-600 hover:shadow-lg hover:shadow-pink-500/40 transition-all"
          >
            <Sparkles className="h-4 w-4 mr-2" />
            Demander à l&apos;IA
          </Button>
        </>
      }
    />
  );
}

import { RhPageHeader } from '@/components/layout';
import { Button } from '@/components/ui/button';
import { Sparkles } from 'lucide-react';

interface DashboardHeaderProps {
  firstName: string;
  dateLabel: string;
  onCopilotClick: () => void;
  onGeneratePayrollClick: () => void;
}

export function DashboardHeader({
  firstName,
  dateLabel,
  onCopilotClick,
  onGeneratePayrollClick,
}: DashboardHeaderProps) {
  return (
    <RhPageHeader
      title={`Bonjour ${firstName},`}
      description={dateLabel}
      afterDescription={<p className="text-sm text-muted-foreground">Cockpit de pilotage RH</p>}
      actions={
        <>
          <Button variant="outline" onClick={onGeneratePayrollClick}>
            <Sparkles className="h-4 w-4 mr-2" />
            Générer la paie
          </Button>
          <Button onClick={onCopilotClick}>
            <Sparkles className="h-4 w-4 mr-2" />
            Demander à l&apos;IA
          </Button>
        </>
      }
    />
  );
}

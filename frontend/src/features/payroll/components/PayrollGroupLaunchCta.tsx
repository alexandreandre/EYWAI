import { Link, useLocation } from 'react-router-dom';
import { etatPourModeGroupe } from '@/features/payroll/utils/retourModeGroupe';
import { Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function PayrollGroupLaunchCta() {
  const location = useLocation();
  return (
    <div className="flex justify-center">
      <Button className="gap-1.5" asChild>
        <Link to="/payroll/generate" state={etatPourModeGroupe(location)}>
          <Sparkles className="h-4 w-4" />
          Lancer la paie (Mode Groupé)
        </Link>
      </Button>
    </div>
  );
}

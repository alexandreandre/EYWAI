import { Link } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function PayrollGroupLaunchCta() {
  return (
    <div className="flex justify-center">
      <Button className="gap-1.5" asChild>
        <Link to="/payroll/generate">
          <Sparkles className="h-4 w-4" />
          Lancer la paie (Mode Groupé)
        </Link>
      </Button>
    </div>
  );
}

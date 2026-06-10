import { useState } from 'react';
import { ChevronDown, ChevronRight, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { PAYROLL_REQUIRED_FIELD_LABELS } from '@/features/payroll/constants';
import { PayrollIncompleteEmployeeList } from '@/features/payroll/components/PayrollIncompleteEmployeeList';
import type { PayrollGenerateEmployee } from '@/features/payroll/types';
import { cn } from '@/lib/utils';

type PayrollEmployeeReadinessAlertProps = {
  employees: PayrollGenerateEmployee[];
  onNavigateTo?: (path: string) => void;
};

export function PayrollEmployeeReadinessAlert({
  employees,
  onNavigateTo,
}: PayrollEmployeeReadinessAlertProps) {
  const ineligible = employees.filter((e) => e.payroll_eligible === false);
  const eligibleCount = employees.length - ineligible.length;
  const allBlocked = eligibleCount === 0;
  const [detailOpen, setDetailOpen] = useState(false);

  if (ineligible.length === 0) return null;

  return (
    <div className="rounded-lg border border-amber-200/70 bg-gradient-to-b from-amber-50/40 to-background px-4 py-3.5">
      <div className="flex gap-3">
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber-100/80 text-amber-700">
          <Users className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0 flex-1 space-y-2">
          <div>
            <p className="text-sm font-semibold text-foreground">
              {allBlocked
                ? 'Fiches à compléter avant génération'
                : `${ineligible.length} fiche${ineligible.length > 1 ? 's' : ''} à compléter`}
            </p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {allBlocked
                ? 'Aucun collaborateur ne peut être sélectionné tant que les informations paie ne sont pas renseignées.'
                : 'Seuls les collaborateurs dont la fiche est complète peuvent être sélectionnés.'}
            </p>
          </div>

          <p className="text-xs text-muted-foreground">
            Champs requis&nbsp;: {PAYROLL_REQUIRED_FIELD_LABELS.join(' · ')}
          </p>

          <div className="flex flex-wrap items-center gap-2 pt-0.5">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8 text-xs"
              onClick={() => onNavigateTo?.('/employees')}
            >
              Liste des collaborateurs
              <ChevronRight className="ml-1 h-3.5 w-3.5" />
            </Button>

            <Collapsible open={detailOpen} onOpenChange={setDetailOpen}>
              <CollapsibleTrigger asChild>
                <Button
                  type="button"
                  size="sm"
                  variant={detailOpen ? 'secondary' : 'ghost'}
                  className="h-8 gap-1 text-xs"
                >
                  Détail
                  <ChevronDown
                    className={cn(
                      'h-3.5 w-3.5 transition-transform',
                      detailOpen && 'rotate-180',
                    )}
                  />
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="pt-3">
                <PayrollIncompleteEmployeeList
                  employees={ineligible}
                  onGoToEmployee={(id) => onNavigateTo?.(`/employees/${id}`)}
                />
              </CollapsibleContent>
            </Collapsible>
          </div>
        </div>
      </div>
    </div>
  );
}

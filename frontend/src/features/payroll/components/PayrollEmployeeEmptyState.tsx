import { useState, type ReactNode } from 'react';
import {
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Loader2,
  RefreshCw,
  UserPlus,
  Users,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { PAYROLL_REQUIRED_FIELD_LABELS } from '@/features/payroll/constants';
import {
  libelleStatutSalarie,
  MESSAGE_STATUTS_PRIS_EN_COMPTE,
  statutPermetLaPaie,
} from '@/features/payroll/utils/statutsPaie';
import { messageAucunSelectionnable } from '@/features/payroll/utils/ficheIncomplete';
import { PayrollIncompleteEmployeeList } from '@/features/payroll/components/PayrollIncompleteEmployeeList';
import type { PayrollGenerateEmployee } from '@/features/payroll/types';
import type { EmployeeListItem } from '@/hooks/queries/useEmployeesQuery';
import { cn } from '@/lib/utils';

function toPayrollEmployee(emp: EmployeeListItem): PayrollGenerateEmployee {
  return {
    id: emp.id,
    first_name: emp.first_name,
    last_name: emp.last_name,
    employment_status: emp.employment_status,
    payroll_eligible: emp.payroll_eligible,
    missing_payroll_fields: emp.missing_payroll_fields,
  };
}

type PayrollEmployeeEmptyStateProps = {
  loading: boolean;
  errorMessage?: string | null;
  onRetry?: () => void;
  allEmployees: EmployeeListItem[];
  onNavigateTo?: (path: string) => void;
};

function EmptyStateShell({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: typeof Users;
  title: string;
  description: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border/80 bg-muted/20 px-4 py-3.5">
      <div className="flex gap-3">
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Icon className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0 flex-1 space-y-2">
          <div>
            <p className="text-sm font-semibold text-foreground">{title}</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{description}</p>
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}

export function PayrollEmployeeEmptyState({
  loading,
  errorMessage,
  onRetry,
  allEmployees,
  onNavigateTo,
}: PayrollEmployeeEmptyStateProps) {
  const [detailOpen, setDetailOpen] = useState(false);

  if (loading) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border/70 px-4 py-10 text-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Chargement des collaborateurs…</p>
      </div>
    );
  }

  if (errorMessage) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3.5">
        <div className="flex gap-3">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
          <div className="space-y-2">
            <p className="text-sm font-semibold text-destructive">
              Impossible de charger les collaborateurs
            </p>
            <p className="text-xs text-destructive/90">{errorMessage}</p>
            {onRetry && (
              <Button type="button" size="sm" variant="outline" onClick={onRetry} className="h-8 gap-2 text-xs">
                <RefreshCw className="h-3.5 w-3.5" />
                Réessayer
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  }

  const total = allEmployees.length;
  const launchEligible = allEmployees.filter((e) =>
    statutPermetLaPaie(e.employment_status),
  );
  const excluded = allEmployees.filter(
    (e) => !statutPermetLaPaie(e.employment_status),
  );
  const statusCounts = excluded.reduce<Record<string, number>>((acc, emp) => {
    const label = libelleStatutSalarie(emp.employment_status);
    acc[label] = (acc[label] ?? 0) + 1;
    return acc;
  }, {});

  const detailEmployees = launchEligible.map(toPayrollEmployee);

  if (launchEligible.length > 0) {
    const message = messageAucunSelectionnable(detailEmployees);
    return (
      <EmptyStateShell icon={Users} title={message.titre} description={message.description}>
        {message.fichesACompleter && (
          <p className="text-xs text-muted-foreground">
            Champs requis&nbsp;: {PAYROLL_REQUIRED_FIELD_LABELS.join(' · ')}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-2">
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
          {message.fichesACompleter && (
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
                  className={cn('h-3.5 w-3.5 transition-transform', detailOpen && 'rotate-180')}
                />
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="pt-3">
              <PayrollIncompleteEmployeeList
                employees={detailEmployees}
                onGoToEmployee={(id) => onNavigateTo?.(`/employees/${id}`)}
              />
            </CollapsibleContent>
          </Collapsible>
          )}
        </div>
      </EmptyStateShell>
    );
  }

  if (total === 0) {
    return (
      <EmptyStateShell
        icon={UserPlus}
        title="Aucun collaborateur enregistré"
        description="Créez un collaborateur, passez-le en Actif, puis complétez sa fiche paie."
      >
        <p className="text-xs text-muted-foreground">
          Champs requis&nbsp;: {PAYROLL_REQUIRED_FIELD_LABELS.join(' · ')}
        </p>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-8 text-xs"
          onClick={() => onNavigateTo?.('/employees')}
        >
          Créer ou gérer les collaborateurs
          <ChevronRight className="ml-1 h-3.5 w-3.5" />
        </Button>
      </EmptyStateShell>
    );
  }

  return (
    <EmptyStateShell
      icon={Users}
      title={`${total} collaborateur${total > 1 ? 's' : ''} en base — aucun sélectionnable`}
      description={
        MESSAGE_STATUTS_PRIS_EN_COMPTE
      }
    >
      {excluded.length > 0 && (
        <div className="rounded-md border bg-background/60 px-3 py-2 text-xs text-muted-foreground">
          <p className="mb-1 font-medium text-foreground">Autres statuts</p>
          <ul className="space-y-0.5">
            {Object.entries(statusCounts).map(([label, count]) => (
              <li key={label}>
                {count} × {label}
              </li>
            ))}
          </ul>
        </div>
      )}
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="h-8 text-xs"
        onClick={() => onNavigateTo?.('/employees')}
      >
        Voir les {total} collaborateurs
        <ChevronRight className="ml-1 h-3.5 w-3.5" />
      </Button>
    </EmptyStateShell>
  );
}

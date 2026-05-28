import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import {
  PageHeader,
  pageTitleClassName,
} from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/** Classes communes pour les titres de page employé (détail avec retour, etc.). */
export const employeePageTitleClassName = pageTitleClassName;

/** Conteneur standard : titre aligné à gauche du contenu principal (`main`). */
export const employeePageClassName = 'w-full space-y-6';

type EmployeePageShellProps = {
  children: ReactNode;
  className?: string;
};

export function EmployeePageShell({ children, className }: EmployeePageShellProps) {
  return <div className={cn(employeePageClassName, className)}>{children}</div>;
}

type EmployeePageBackLinkProps = {
  to: string;
  label?: string;
};

/** Lien retour aligné avec les en-têtes de page collaborateur. */
export function EmployeePageBackLink({ to, label = 'Retour' }: EmployeePageBackLinkProps) {
  return (
    <Button
      variant="ghost"
      size="sm"
      className="-ml-2 h-8 w-fit text-muted-foreground"
      asChild
    >
      <Link to={to}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        {label}
      </Link>
    </Button>
  );
}

type EmployeePageHeaderProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
  back?: ReactNode;
  /** Icône affichée à gauche du titre (ex. lucide-react). */
  icon?: ReactNode;
  /** Contenu optionnel sous la description (badges, métadonnées). */
  afterDescription?: ReactNode;
  className?: string;
  /** Centre le bloc titre (écrans d'état restreints). */
  centered?: boolean;
};

export function EmployeePageHeader(props: EmployeePageHeaderProps) {
  return <PageHeader {...props} />;
}

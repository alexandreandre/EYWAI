import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

/** Titre de page standard (interface RH, admin, employé). */
export const pageTitleClassName =
  'text-2xl font-semibold tracking-tight text-foreground';

/** @deprecated Utiliser `pageTitleClassName`. */
export const rhPageTitleClassName = pageTitleClassName;

type PageHeaderProps = {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  /** Lien ou bouton retour affiché au-dessus du titre (pages de détail). */
  back?: ReactNode;
  /** Icône affichée à gauche du titre (ex. lucide-react). */
  icon?: ReactNode;
  /** Contenu optionnel sous la description (badges, métadonnées). */
  afterDescription?: ReactNode;
  className?: string;
  /** Centre le bloc titre (écrans d'état restreints). */
  centered?: boolean;
};

export function PageHeader({
  title,
  description,
  actions,
  back,
  icon,
  afterDescription,
  className,
  centered = false,
}: PageHeaderProps) {
  const titleBlock = (
    <div className={cn('min-w-0 space-y-3', centered && 'text-center')}>
      {back ? <div className={cn('print:hidden', centered && 'flex justify-center')}>{back}</div> : null}
      <div className={cn('min-w-0', centered && 'text-center')}>
        <h1
          className={cn(
            pageTitleClassName,
            icon && 'flex items-center gap-2',
            centered && 'justify-center'
          )}
        >
          {icon ? (
            <span className="shrink-0 text-primary [&>svg]:h-7 [&>svg]:w-7" aria-hidden>
              {icon}
            </span>
          ) : null}
          {title}
        </h1>
        {description ? (
          <p
            className={cn(
              'mt-1 text-sm text-muted-foreground',
              centered && 'text-center'
            )}
          >
            {description}
          </p>
        ) : null}
        {afterDescription ? <div className="mt-2">{afterDescription}</div> : null}
      </div>
    </div>
  );

  if (centered) {
    return <div className={cn('space-y-2', className)}>{titleBlock}</div>;
  }

  return (
    <div
      className={cn(
        'flex flex-wrap items-start justify-between gap-4',
        className
      )}
    >
      {titleBlock}
      {actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </div>
  );
}

/** En-tête standard des pages de l'interface RH. */
export const RhPageHeader = PageHeader;

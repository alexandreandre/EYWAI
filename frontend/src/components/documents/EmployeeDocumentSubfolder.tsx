import { Link } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { EmployeeGroupMeta } from '@/components/documents/companyDocumentsExplorerUtils';
import { ChevronDown, ExternalLink, Folder, FolderOpen, User } from 'lucide-react';
import type { ReactNode } from 'react';

function employeeDetailHref(employeeId: string) {
  return `/employees/${employeeId}?tab=documents`;
}

export interface EmployeeDocumentSubfolderProps {
  meta: EmployeeGroupMeta;
  fileCount: number;
  isOpen: boolean;
  onToggle: () => void;
  children: ReactNode;
  /** Variante compacte dans la liste latérale employés (desktop). */
  variant?: 'accordion' | 'sidebar-item';
  isSelected?: boolean;
  onSelect?: () => void;
}

export function EmployeeDocumentSubfolder({
  meta,
  fileCount,
  isOpen,
  onToggle,
  children,
  variant = 'accordion',
}: EmployeeDocumentSubfolderProps) {
  const Icon = isOpen ? FolderOpen : Folder;
  const canLink = meta.employeeId !== '__unknown__';

  if (variant === 'sidebar-item') {
    return (
      <div className="min-w-0">
        <button
          type="button"
          onClick={onToggle}
          className={cn(
            'flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors',
            isOpen
              ? 'bg-primary/10 text-primary font-medium'
              : 'text-foreground hover:bg-muted/80'
          )}
        >
          <User className="h-4 w-4 shrink-0 opacity-80" aria-hidden />
          <span className="min-w-0 flex-1 truncate">{meta.employeeName}</span>
          <Badge variant="secondary" className="shrink-0 tabular-nums text-xs">
            {fileCount}
          </Badge>
        </button>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-md border border-border/60">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-2 bg-muted/30 px-3 py-2.5 text-left text-sm transition-colors hover:bg-muted/50"
        aria-expanded={isOpen}
      >
        <Icon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
        <span className="min-w-0 flex-1 font-medium leading-snug">
          {canLink ? (
            <Link
              to={employeeDetailHref(meta.employeeId)}
              className="hover:text-primary hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {meta.employeeName}
            </Link>
          ) : (
            meta.employeeName
          )}
        </span>
        {canLink && (
          <Link
            to={employeeDetailHref(meta.employeeId)}
            className="shrink-0 text-muted-foreground hover:text-primary"
            onClick={(e) => e.stopPropagation()}
            title="Ouvrir la fiche"
          >
            <ExternalLink className="h-3.5 w-3.5" aria-hidden />
            <span className="sr-only">Fiche collaborateur</span>
          </Link>
        )}
        <Badge variant="secondary" className="shrink-0 tabular-nums">
          {fileCount}
        </Badge>
        <ChevronDown
          className={cn('h-4 w-4 shrink-0 text-muted-foreground transition-transform', isOpen && 'rotate-180')}
          aria-hidden
        />
      </button>
      {isOpen && <div className="border-t bg-background p-1">{children}</div>}
    </div>
  );
}

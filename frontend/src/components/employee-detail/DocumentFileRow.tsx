import { ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { FileText, Download, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface DocumentFileRowProps {
  name: string;
  subtitle?: ReactNode;
  meta?: ReactNode;
  actions: ReactNode;
  className?: string;
}

export function DocumentFileRow({ name, subtitle, meta, actions, className }: DocumentFileRowProps) {
  return (
    <li
      className={cn(
        'flex flex-col gap-2 rounded-md border border-transparent p-3 transition-colors sm:flex-row sm:items-center sm:justify-between hover:bg-muted/60 hover:border-border',
        className
      )}
    >
      <div className="flex min-w-0 flex-1 items-start gap-3">
        <FileText className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-medium leading-snug">{name}</p>
          {subtitle && <div className="mt-1 text-sm text-muted-foreground">{subtitle}</div>}
          {meta && <div className="mt-1.5 flex flex-wrap items-center gap-2">{meta}</div>}
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">{actions}</div>
    </li>
  );
}

export function DownloadLinkButton({
  href,
  download,
  label = 'Télécharger',
  disabled,
}: {
  href: string;
  download?: string;
  label?: string;
  disabled?: boolean;
}) {
  return (
    <Button variant="outline" size="sm" asChild disabled={disabled}>
      <a href={href} download={download} target="_blank" rel="noopener noreferrer">
        <Download className="mr-2 h-4 w-4" />
        {label}
      </a>
    </Button>
  );
}

export function DownloadIconButton({
  href,
  download,
  loading,
}: {
  href: string;
  download?: string;
  loading?: boolean;
}) {
  return (
    <Button variant="ghost" size="icon" asChild disabled={loading}>
      <a href={href} download={download} target="_blank" rel="noopener noreferrer">
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
        <span className="sr-only">Télécharger</span>
      </a>
    </Button>
  );
}

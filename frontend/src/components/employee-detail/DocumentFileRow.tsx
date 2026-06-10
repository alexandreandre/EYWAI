import { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { openSignedUrlPreview } from '@/lib/openSignedUrlPreview';
import { Download, Eye, FileText, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface DocumentFileRowProps {
  name: ReactNode;
  subtitle?: ReactNode;
  meta?: ReactNode;
  actions: ReactNode;
  className?: string;
  /** Rend la zone principale cliquable (ex. fiche bulletin). */
  rowHref?: string;
}

export function DocumentFileRow({ name, subtitle, meta, actions, className, rowHref }: DocumentFileRowProps) {
  const inner = (
    <>
      <FileText className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5 font-medium leading-snug">{name}</p>
        {subtitle && <div className="mt-1 text-sm text-muted-foreground">{subtitle}</div>}
        {meta && <div className="mt-1.5 flex flex-wrap items-center gap-2">{meta}</div>}
      </div>
    </>
  );

  return (
    <li
      className={cn(
        'flex flex-col gap-2 rounded-md border border-transparent p-3 transition-colors sm:flex-row sm:items-center sm:justify-between hover:bg-muted/60 hover:border-border',
        className
      )}
    >
      <div className="flex min-w-0 flex-1 items-start gap-3">
        {rowHref ? (
          <Link
            to={rowHref}
            className="flex min-w-0 flex-1 items-start gap-3 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {inner}
          </Link>
        ) : (
          inner
        )}
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">{actions}</div>
    </li>
  );
}

export function ViewLinkButton({
  href,
  title = 'Visualiser',
  disabled,
  downloadUrl,
  downloadName,
}: {
  href: string;
  title?: string;
  disabled?: boolean;
  /** URL de téléchargement (si différente de l’aperçu). */
  downloadUrl?: string;
  downloadName?: string;
}) {
  const isDisabled = disabled || !href?.trim();
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className="h-8 w-8"
      disabled={isDisabled}
      title={title}
      onClick={() =>
        openSignedUrlPreview(href, {
          title,
          downloadUrl: downloadUrl ?? href,
          downloadName,
        })
      }
    >
      <Eye className="h-4 w-4" />
      <span className="sr-only">{title}</span>
    </Button>
  );
}

export function DocumentPreviewDownloadActions({
  previewUrl,
  downloadUrl,
  downloadName,
  previewTitle = 'Visualiser',
  downloadLabel = 'Télécharger',
}: {
  previewUrl?: string | null;
  downloadUrl: string;
  downloadName?: string;
  previewTitle?: string;
  downloadLabel?: string;
}) {
  return (
    <>
      <ViewLinkButton
        href={previewUrl ?? downloadUrl}
        title={previewTitle}
        downloadUrl={downloadUrl}
        downloadName={downloadName}
      />
      <DownloadLinkButton href={downloadUrl} download={downloadName} label={downloadLabel} />
    </>
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

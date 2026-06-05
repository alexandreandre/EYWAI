import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  getReadinessLabel,
  getTextAvailabilityLabel,
  type ReadinessLevel,
} from '@/lib/collectiveAgreementReadiness';
import { cn } from '@/lib/utils';
import { SharkFinBootProgress } from '@/components/SharkFinBootProgress';
import {
  Building2,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  CircleDashed,
  Download,
  Edit,
  ExternalLink,
  Eye,
  FileText,
  Loader2,
  MessageSquare,
  MoreVertical,
  RefreshCw,
  Sparkles,
  Trash2,
  X,
  XCircle,
} from 'lucide-react';

export type DocumentLoadingKind =
  | 'full-text'
  | 'synthesis'
  | 'rules'
  | 'sync';

export type CollectiveAgreementRowProps = {
  variant: 'rh' | 'admin';
  name: string;
  idcc: string;
  sector?: string | null;
  isActive?: boolean;
  readiness: ReadinessLevel;
  hasText: boolean;
  legifranceUrl?: string | null;
  hasRules: boolean;
  hasPayrollGrid?: boolean;
  payrollGridUnavailableReason?: string | null;
  hasUploadedPdf?: boolean;
  loading?: DocumentLoadingKind | null;
  onAskQuestion?: () => void;
  onViewFullText?: () => void;
  onViewSynthesis?: () => void;
  onExportRulesPdf?: () => void;
  onDownloadSourcePdf?: () => void;
  onSync?: () => void;
  onCancelSync?: () => void;
  isCancellingSync?: boolean;
  onAssignToCompany?: () => void;
  onViewTechnical?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  onUnassign?: () => void;
};

function ReadinessChip({ level }: { level: ReadinessLevel }) {
  const config = {
    ready: {
      icon: CheckCircle2,
      className: 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300',
    },
    partial: {
      icon: CircleAlert,
      className: 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300',
    },
    missing: {
      icon: CircleDashed,
      className: 'border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-400',
    },
  }[level];

  const Icon = config.icon;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        config.className
      )}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" />
      {getReadinessLabel(level)}
    </span>
  );
}

function TextChip({
  hasText,
  legifranceUrl,
  onOpenOfficialText,
  isLoading,
}: {
  hasText: boolean;
  legifranceUrl?: string | null;
  onOpenOfficialText?: () => void;
  isLoading?: boolean;
}) {
  const chipClass = cn(
    'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium',
    hasText
      ? 'border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-300'
      : 'border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-400'
  );

  const linkClass = cn(
    'inline-flex items-center gap-1.5 font-medium underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1',
    hasText && 'cursor-pointer'
  );

  if (!hasText) {
    return (
      <span className={chipClass}>
        <XCircle className="h-3.5 w-3.5 shrink-0" />
        {getTextAvailabilityLabel(false)}
      </span>
    );
  }

  const label = getTextAvailabilityLabel(true);
  const icon = isLoading ? (
    <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
  ) : legifranceUrl ? (
    <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden />
  ) : (
    <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden />
  );

  if (legifranceUrl) {
    return (
      <a
        href={legifranceUrl}
        target="_blank"
        rel="noopener noreferrer"
        className={cn(chipClass, linkClass)}
        title="Ouvrir le texte officiel sur Légifrance"
      >
        {icon}
        {label}
      </a>
    );
  }

  if (onOpenOfficialText) {
    return (
      <button
        type="button"
        onClick={onOpenOfficialText}
        disabled={isLoading}
        className={cn(chipClass, linkClass)}
        title="Ouvrir le texte intégral de la convention"
      >
        {icon}
        {label}
      </button>
    );
  }

  return (
    <span className={chipClass}>
      <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
      {label}
    </span>
  );
}

function ActiveChip({ isActive }: { isActive: boolean }) {
  if (isActive) {
    return (
      <Badge variant="default" className="bg-emerald-600 hover:bg-emerald-600">
        Actif
      </Badge>
    );
  }
  return <Badge variant="secondary">Inactif</Badge>;
}

export function CollectiveAgreementRow({
  variant,
  name,
  idcc,
  sector,
  isActive = true,
  readiness,
  hasText,
  legifranceUrl,
  hasRules,
  hasPayrollGrid = hasRules,
  payrollGridUnavailableReason,
  hasUploadedPdf,
  loading,
  onAskQuestion,
  onViewFullText,
  onViewSynthesis,
  onExportRulesPdf,
  onDownloadSourcePdf,
  onSync,
  onCancelSync,
  isCancellingSync = false,
  onAssignToCompany,
  onViewTechnical,
  onEdit,
  onDelete,
  onUnassign,
}: CollectiveAgreementRowProps) {
  const isDocLoading = (kind: DocumentLoadingKind) => loading === kind;
  const isUpdating = loading === 'sync';
  const canDownloadDocs = hasText || hasUploadedPdf;

  return (
    <TooltipProvider delayDuration={300}>
      <div
        className={cn(
          'relative overflow-hidden rounded-lg border bg-card transition-colors hover:bg-muted/20'
        )}
      >
        {isUpdating && (
          <div
            className="absolute inset-0 z-10 flex flex-col items-center justify-center rounded-lg bg-background/80 backdrop-blur-[1px]"
            role="status"
            aria-live="polite"
            aria-busy="true"
            aria-label="Mise à jour de la convention depuis Légifrance"
          >
            {onCancelSync && (
              <button
                type="button"
                className="absolute right-2 top-2 z-20 flex h-7 w-7 items-center justify-center rounded-md text-red-600 transition-colors hover:bg-red-50 hover:text-red-700 disabled:opacity-50 dark:hover:bg-red-950/40"
                onClick={onCancelSync}
                disabled={isCancellingSync}
                aria-label="Annuler la mise à jour Légifrance"
              >
                {isCancellingSync ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <X className="h-4 w-4" />
                )}
              </button>
            )}
            <div className="w-full max-w-sm px-5">
              <SharkFinBootProgress className="pt-5 pb-1" />
              <p className="mt-2 text-center text-xs text-muted-foreground">
                Mise à jour depuis Légifrance…
              </p>
            </div>
          </div>
        )}

        <div className={cn('p-4 transition-opacity', isUpdating && 'opacity-30')}>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          {/* Identité */}
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex flex-wrap items-start gap-2">
              <h3 className="text-sm font-semibold leading-snug text-foreground">{name}</h3>
              <Badge variant="outline" className="shrink-0 font-mono text-xs">
                IDCC {idcc}
              </Badge>
              {sector && (
                <Badge variant="secondary" className="shrink-0 text-xs">
                  {sector}
                </Badge>
              )}
              {variant === 'admin' && <ActiveChip isActive={isActive} />}
            </div>

            {/* Chips d'état */}
            <div className="flex flex-wrap gap-2">
              <Tooltip>
                <TooltipTrigger asChild>
                  <span>
                    <ReadinessChip level={readiness} />
                  </span>
                </TooltipTrigger>
                <TooltipContent>
                  État de configuration pour le moteur de paie
                </TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span>
                    <TextChip
                      hasText={hasText}
                      legifranceUrl={legifranceUrl}
                      onOpenOfficialText={onViewFullText}
                      isLoading={isDocLoading('full-text')}
                    />
                  </span>
                </TooltipTrigger>
                <TooltipContent>
                  {hasText
                    ? legifranceUrl
                      ? 'Ouvrir le texte officiel sur Légifrance (nouvel onglet)'
                      : 'Ouvrir le texte intégral de la convention (PDF)'
                    : 'Texte non importé — mettez à jour depuis Légifrance'}
                </TooltipContent>
              </Tooltip>
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-wrap items-center gap-2 lg:shrink-0 lg:justify-end">
            {onAskQuestion && (
              <Button
                size="sm"
                onClick={onAskQuestion}
                className="bg-indigo-600 hover:bg-indigo-700"
              >
                <MessageSquare className="mr-2 h-4 w-4" />
                Assistant
              </Button>
            )}

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!canDownloadDocs && !hasRules}
                >
                  {loading && ['full-text', 'synthesis', 'rules'].includes(loading) ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <FileText className="mr-2 h-4 w-4" />
                  )}
                  Documents
                  <ChevronDown className="ml-1 h-3.5 w-3.5 opacity-60" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                <DropdownMenuItem
                  disabled={!hasText || isDocLoading('full-text')}
                  onClick={onViewFullText}
                >
                  {isDocLoading('full-text') ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Eye className="mr-2 h-4 w-4" />
                  )}
                  Convention complète
                </DropdownMenuItem>
                <DropdownMenuItem
                  disabled={!hasText || isDocLoading('synthesis')}
                  onClick={onViewSynthesis}
                >
                  {isDocLoading('synthesis') ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="mr-2 h-4 w-4 text-violet-600" />
                  )}
                  Guide simplifié
                </DropdownMenuItem>
                <DropdownMenuItem
                  disabled={!hasPayrollGrid || isDocLoading('rules')}
                  onClick={onExportRulesPdf}
                  title={!hasPayrollGrid ? payrollGridUnavailableReason ?? undefined : undefined}
                >
                  {isDocLoading('rules') ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <FileText className="mr-2 h-4 w-4" />
                  )}
                  Grille des salaires
                </DropdownMenuItem>
                {hasUploadedPdf && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={onDownloadSourcePdf}>
                      <Download className="mr-2 h-4 w-4" />
                      PDF source
                    </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
                  <MoreVertical className="h-4 w-4" />
                  <span className="sr-only">Plus d&apos;actions</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                {variant === 'admin' ? (
                  <>
                    <DropdownMenuItem disabled={isUpdating} onClick={onSync}>
                      {isUpdating ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="mr-2 h-4 w-4" />
                      )}
                      Mettre à jour
                    </DropdownMenuItem>
                    {onAssignToCompany && (
                      <DropdownMenuItem onClick={onAssignToCompany}>
                        <Building2 className="mr-2 h-4 w-4" />
                        Assigner à une entreprise
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuItem disabled={!hasRules} onClick={onViewTechnical}>
                      <Eye className="mr-2 h-4 w-4" />
                      Détail technique
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={onEdit}>
                      <Edit className="mr-2 h-4 w-4" />
                      Modifier
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={onDelete}
                      className="text-red-600 focus:text-red-600"
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Supprimer
                    </DropdownMenuItem>
                  </>
                ) : (
                  <DropdownMenuItem
                    onClick={onUnassign}
                    className="text-red-600 focus:text-red-600"
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Retirer
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}

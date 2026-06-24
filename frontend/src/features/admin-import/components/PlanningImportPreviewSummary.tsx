import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import type { PlanningImportSummary } from '@/api/adminImport';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

function statusMeta(status: PlanningImportSummary['validation_status']) {
  if (status === 'ok') {
    return {
      label: 'Prêt à enregistrer',
      icon: CheckCircle2,
      className: 'text-emerald-700',
    };
  }
  if (status === 'warning') {
    return {
      label: 'Import possible avec réserves',
      icon: AlertTriangle,
      className: 'text-amber-800',
    };
  }
  return {
    label: 'Rapprochement insuffisant',
    icon: XCircle,
    className: 'text-destructive',
  };
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium tabular-nums">{value}</dd>
    </div>
  );
}

type Props = {
  summary: PlanningImportSummary;
};

export function PlanningImportPreviewSummary({ summary }: Props) {
  const meta = statusMeta(summary.validation_status);
  const Icon = meta.icon;

  return (
    <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className={cn('flex items-center gap-2 text-sm font-medium', meta.className)}>
          <Icon className="h-4 w-4 shrink-0" aria-hidden />
          {meta.label}
        </div>
        <Badge variant="secondary" className="max-w-[16rem] truncate font-normal">
          {summary.format_label}
        </Badge>
      </div>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Période" value={summary.period_label} />
        <Stat label="Feuilles lues" value={summary.sheets_parsed ?? '—'} />
        <Stat
          label="Salariés reconnus"
          value={`${summary.employees_importable} / ${summary.employees_total}`}
        />
        <Stat label="Jours calendrier" value={summary.days_total.toLocaleString('fr-FR')} />
      </dl>

      <div className="flex flex-wrap gap-2 text-xs">
        {summary.employees_ok > 0 ? (
          <Badge variant="secondary" className="bg-emerald-50 text-emerald-800">
            {summary.employees_ok} prêt{summary.employees_ok > 1 ? 's' : ''}
          </Badge>
        ) : null}
        {summary.employees_warning > 0 ? (
          <Badge variant="secondary" className="bg-amber-50 text-amber-900">
            {summary.employees_warning} à vérifier
          </Badge>
        ) : null}
        {summary.employees_error > 0 ? (
          <Badge variant="secondary" className="bg-red-50 text-red-800">
            {summary.employees_error} non rapproché{summary.employees_error > 1 ? 's' : ''}
          </Badge>
        ) : null}
      </div>

      <p className="text-xs leading-relaxed text-muted-foreground">{summary.commit_hint}</p>

      {summary.warnings.length > 0 && summary.review_items.length === 0 ? (
        <ul className="space-y-1 text-xs text-muted-foreground">
          {summary.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

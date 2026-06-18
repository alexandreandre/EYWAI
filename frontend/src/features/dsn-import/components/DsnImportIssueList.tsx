import type { DsnImportCommitResponse, DsnImportIssue } from '@/api/dsnImport';
import { cn } from '@/lib/utils';

import { DSN_IMPORT_ISSUE_HINTS } from '../constants';

type DsnImportIssueListProps = {
  title: string;
  issues: DsnImportIssue[];
  onClickRef?: (ref: string) => void;
  tone?: 'blocking' | 'warning' | 'error';
};

function issueHint(issue: DsnImportIssue): string | null {
  if (issue.hint) return issue.hint;
  const code = issue.code;
  return code ? DSN_IMPORT_ISSUE_HINTS[code] ?? null : null;
}

export function DsnImportIssueList({
  title,
  issues,
  onClickRef,
  tone = 'warning',
}: DsnImportIssueListProps) {
  if (!issues.length) return null;

  const messageClass =
    tone === 'blocking' || tone === 'error'
      ? 'text-destructive'
      : 'text-muted-foreground';

  return (
    <div>
      <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
      <ul className="space-y-2">
        {issues.map((issue, index) => {
          const hint = issueHint(issue);
          const content = (
            <span className="block">
              <span className={cn('font-medium leading-snug', messageClass)}>{issue.message}</span>
              {hint && (
                <span className="mt-0.5 block text-xs leading-snug text-muted-foreground">
                  {hint}
                </span>
              )}
              {issue.code && (
                <span className="mt-1 block font-mono text-[10px] text-muted-foreground/70">
                  {issue.code}
                </span>
              )}
            </span>
          );

          return (
            <li key={`${issue.code}-${issue.source_ref ?? index}`}>
              {issue.source_ref && onClickRef ? (
                <button
                  type="button"
                  className={cn(
                    'w-full text-left underline decoration-dotted underline-offset-2 hover:text-foreground',
                    messageClass,
                  )}
                  onClick={() => onClickRef(issue.source_ref!)}
                >
                  {content}
                </button>
              ) : (
                content
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function normalizeCommitErrors(
  errors: DsnImportCommitResponse['errors'] | string[] | undefined,
  errorMessages?: string[],
): DsnImportIssue[] {
  const raw = errors ?? [];
  if (raw.length > 0) {
    return raw.map((entry) => {
      if (typeof entry === 'string') {
        return {
          code: 'unknown',
          message: entry,
          severity: 'error',
        };
      }
      return {
        code: entry.code || 'unknown',
        message: entry.message,
        hint: entry.hint,
        severity: entry.severity || 'error',
        source_ref: entry.source_ref,
        item_label: entry.item_label,
        meta: entry.meta,
      };
    });
  }
  return (errorMessages ?? []).map((message) => ({
    code: 'unknown',
    message,
    severity: 'error',
  }));
}

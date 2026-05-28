import { Download, Eye } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { Expense } from '@/api/expenses';

interface EmployeeExpenseReceiptActionsProps {
  expense: Expense;
  onDownload: (expense: Expense) => void;
  compact?: boolean;
}

export function EmployeeExpenseReceiptActions({
  expense,
  onDownload,
  compact = false,
}: EmployeeExpenseReceiptActionsProps) {
  if (!expense.receipt_url) {
    return <span className="text-sm text-muted-foreground">Non joint</span>;
  }

  return (
    <div className={compact ? 'flex gap-1' : 'flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-2'}>
      <div className="flex gap-1">
        <Button variant="outline" size="icon" className="h-8 w-8" asChild>
          <a
            href={expense.receipt_url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Voir le justificatif"
            title="Voir le justificatif"
          >
            <Eye className="h-4 w-4" />
          </a>
        </Button>
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8"
          onClick={() => onDownload(expense)}
          aria-label="Télécharger le justificatif"
          title="Télécharger le justificatif"
        >
          <Download className="h-4 w-4" />
        </Button>
      </div>
      {expense.filename && (
        <span className="max-w-[140px] truncate text-xs text-muted-foreground" title={expense.filename}>
          {expense.filename}
        </span>
      )}
    </div>
  );
}

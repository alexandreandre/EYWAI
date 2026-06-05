import type { PayslipInfo } from '@/api/payslips';
import { monthLabel, monthYearLabel, PAYROLL_MONTHS } from '@/features/payroll/utils/payrollMonth';
import { PayrollMonthListSkeleton } from '@/features/payroll/components/PayrollSkeletons';
import {
  PayrollPayslipRow,
  type PayslipRowStatus,
} from '@/features/payroll/components/PayrollPayslipRow';

export type MonthRowStatus = PayslipRowStatus;

export type MonthStatusMap = Record<
  number,
  { status: MonthRowStatus; payslip?: PayslipInfo; errorMessage?: string }
>;

type PayrollMonthListProps = {
  selectedYear: number;
  monthStatuses: MonthStatusMap;
  loadingPayslips: boolean;
  onGenerateMonth: (month: number) => void;
  onDeletePayslip: (payslipId: string) => void;
  deletingPayslipId: string | null;
};

export function PayrollMonthList({
  selectedYear,
  monthStatuses,
  loadingPayslips,
  onGenerateMonth,
  onDeletePayslip,
  deletingPayslipId,
}: PayrollMonthListProps) {
  if (loadingPayslips) {
    return <PayrollMonthListSkeleton />;
  }

  return (
    <ul className="divide-y divide-border/60">
      {PAYROLL_MONTHS.map((month) => {
        const info = monthStatuses[month] ?? { status: 'idle' as const };
        return (
          <PayrollPayslipRow
            key={month}
            name={monthLabel(month)}
            state={info}
            onGenerate={() => onGenerateMonth(month)}
            onDelete={onDeletePayslip}
            deletingPayslipId={deletingPayslipId}
            deleteDescription={
              <>
                Le bulletin de {monthYearLabel(month, selectedYear)} sera supprimé définitivement.
              </>
            }
          />
        );
      })}
    </ul>
  );
}

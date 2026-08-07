import { PayrollPayslipEditLockCard } from '@/features/admin/components/PayrollPayslipEditLockCard';

export default function PayrollSettings() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Paramètres paie</h1>
        <p className="text-sm text-muted-foreground">
          Réglages globaux de la paie et des bulletins.
        </p>
      </div>
      <PayrollPayslipEditLockCard />
    </div>
  );
}

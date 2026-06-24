import { Banknote } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { maskIban, type EmployeeProfileData } from '@/lib/employeeProfileUtils';

interface EmployeeProfileBankCardProps {
  profile: EmployeeProfileData;
}

export function EmployeeProfileBankCard({ profile }: EmployeeProfileBankCardProps) {
  const iban = profile.coordonnees_bancaires?.iban;
  const paymentMethod = profile.salary_payment_method ?? 'virement';
  const paymentLabel =
    paymentMethod === 'cheque'
      ? 'Chèque'
      : paymentMethod === 'especes'
        ? 'Espèces'
        : 'Virement';

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center">
          <Banknote className="mr-2 h-5 w-5" />
          Données bancaires
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <Label>Mode de paiement du salaire</Label>
          <p className="text-sm font-medium">{paymentLabel}</p>
        </div>
        <div>
          <Label>IBAN actuel</Label>
          <p className="font-mono text-sm font-semibold tracking-wide">
            {maskIban(iban)}
          </p>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Pour modifier votre IBAN, contactez votre service RH avec un nouveau RIB.
        </p>
      </CardContent>
    </Card>
  );
}

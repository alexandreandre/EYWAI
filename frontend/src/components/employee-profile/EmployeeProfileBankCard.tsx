import { Banknote } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { maskIban, type EmployeeProfileData } from '@/lib/employeeProfileUtils';

interface EmployeeProfileBankCardProps {
  profile: EmployeeProfileData;
}

export function EmployeeProfileBankCard({ profile }: EmployeeProfileBankCardProps) {
  const iban = profile.coordonnees_bancaires?.iban;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center">
          <Banknote className="mr-2 h-5 w-5" />
          Données bancaires
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Label>IBAN actuel</Label>
        <p className="font-mono text-sm font-semibold tracking-wide">
          {maskIban(iban)}
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          Pour modifier votre IBAN, contactez votre service RH avec un nouveau RIB.
        </p>
      </CardContent>
    </Card>
  );
}

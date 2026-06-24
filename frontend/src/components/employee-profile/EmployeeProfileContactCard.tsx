import { Home, Mail, Phone } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { formatProfileAddress, getDisplayEmployeeEmail, type EmployeeProfileData } from '@/lib/employeeProfileUtils';

interface EmployeeProfileContactCardProps {
  profile: EmployeeProfileData;
}

function ContactRow({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Home;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start gap-4">
      <Icon className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
      <div className="min-w-0 flex-1">
        <Label className="text-xs text-muted-foreground">{label}</Label>
        <p className="font-semibold break-words">{value}</p>
      </div>
    </div>
  );
}

export function EmployeeProfileContactCard({ profile }: EmployeeProfileContactCardProps) {
  const phone = profile.phone_number?.trim();
  const displayEmail = getDisplayEmployeeEmail(profile.email);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Coordonnées</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <ContactRow
          icon={Home}
          label="Adresse postale"
          value={formatProfileAddress(profile.adresse)}
        />
        {phone ? (
          <ContactRow icon={Phone} label="Téléphone" value={phone} />
        ) : null}
        <ContactRow
          icon={Mail}
          label="Email personnel"
          value={displayEmail || 'Non renseigné'}
        />
      </CardContent>
    </Card>
  );
}

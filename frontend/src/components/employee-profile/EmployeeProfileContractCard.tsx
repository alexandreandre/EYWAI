import { FileText } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  formatProfileDate,
  formatTempsPartielLabel,
  formatTrialPeriodLabel,
  formatWeeklyHours,
  type EmployeeProfileData,
} from '@/lib/employeeProfileUtils';

interface EmployeeProfileContractCardProps {
  profile: EmployeeProfileData;
}

function ReadOnlyField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <p className="font-semibold">{value}</p>
    </div>
  );
}

export function EmployeeProfileContractCard({ profile }: EmployeeProfileContractCardProps) {
  const trialLabel = formatTrialPeriodLabel(profile);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center">
          <FileText className="mr-2 h-5 w-5" />
          Mon Contrat
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <ReadOnlyField label="Poste" value={profile.job_title || 'Non renseigné'} />
          <ReadOnlyField
            label="Type de contrat"
            value={profile.contract_type || 'Non renseigné'}
          />
          <ReadOnlyField label="Date d'arrivée" value={formatProfileDate(profile.hire_date)} />
          <ReadOnlyField label="Statut" value={profile.statut || 'Non renseigné'} />
          <ReadOnlyField
            label="Temps de travail"
            value={formatTempsPartielLabel(profile.is_temps_partiel)}
          />
          <ReadOnlyField
            label="Durée hebdomadaire"
            value={formatWeeklyHours(profile.duree_hebdomadaire)}
          />
          {trialLabel ? (
            <ReadOnlyField label="Période d'essai" value={trialLabel} />
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

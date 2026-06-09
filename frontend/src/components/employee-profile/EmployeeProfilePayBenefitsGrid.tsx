import { FlaskConical, HeartHandshake, Percent, Umbrella } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  formatProfileCurrency,
  getFirstSocialLine,
  getSocialLineAmount,
  type EmployeeProfileData,
} from '@/lib/employeeProfileUtils';

interface EmployeeProfilePayBenefitsGridProps {
  profile: EmployeeProfileData;
}

function AffiliationBadge({ affiliated }: { affiliated: boolean }) {
  return (
    <Badge variant={affiliated ? 'default' : 'secondary'}>
      {affiliated ? 'Affilié' : 'Non affilié'}
    </Badge>
  );
}

export function EmployeeProfilePayBenefitsGrid({ profile }: EmployeeProfilePayBenefitsGridProps) {
  const pasTaux = profile.specificites_paie?.prelevement_a_la_source?.taux;
  const mutuelleAdhesion = profile.specificites_paie?.mutuelle?.adhesion ?? false;
  const prevoyanceAdhesion = profile.specificites_paie?.prevoyance?.adhesion ?? false;
  const jeiEligible =
    profile.specificites_paie?.personnel_rd_eligible_jei
    || profile.specificites_paie?.mandataire_rd
    || false;
  const mutuelleLine = getFirstSocialLine(profile, 'mutuelle');
  const prevoyanceLine = getFirstSocialLine(profile, 'prevoyance');
  const mutuelleAmount = mutuelleLine
    ? formatProfileCurrency(getSocialLineAmount(mutuelleLine, 'mutuelle'))
    : null;
  const prevoyanceAmount = prevoyanceLine
    ? formatProfileCurrency(getSocialLineAmount(prevoyanceLine, 'prevoyance'))
    : null;

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Percent className="mr-2 h-5 w-5" />
            Prélèvement à la Source
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Label>Taux d&apos;imposition</Label>
          <p className="text-2xl font-bold tabular-nums">
            {pasTaux != null ? `${pasTaux}%` : 'Non communiqué'}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            Ce taux est transmis par l&apos;administration fiscale.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0">
          <CardTitle className="flex items-center">
            <HeartHandshake className="mr-2 h-5 w-5" />
            Mutuelle
          </CardTitle>
          <AffiliationBadge affiliated={mutuelleAdhesion} />
        </CardHeader>
        <CardContent className="space-y-2">
          <Label>Organisme</Label>
          <p className="font-semibold">
            {mutuelleLine?.libelle || (mutuelleAdhesion ? 'Affilié' : 'Non affilié')}
          </p>
          {mutuelleAmount ? (
            <>
              <Label>Part salariale</Label>
              <p className="font-semibold tabular-nums">{mutuelleAmount}</p>
            </>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0">
          <CardTitle className="flex items-center">
            <Umbrella className="mr-2 h-5 w-5" />
            Prévoyance
          </CardTitle>
          <AffiliationBadge affiliated={prevoyanceAdhesion} />
        </CardHeader>
        <CardContent className="space-y-2">
          <Label>Organisme</Label>
          <p className="font-semibold">
            {prevoyanceAdhesion
              ? prevoyanceLine?.libelle || 'Affilié'
              : 'Non affilié'}
          </p>
          {prevoyanceAmount ? (
            <>
              <Label>Part salariale</Label>
              <p className="font-semibold tabular-nums">{prevoyanceAmount}</p>
            </>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0">
          <CardTitle className="flex items-center">
            <FlaskConical className="mr-2 h-5 w-5" />
            Exonération JEI
          </CardTitle>
          <AffiliationBadge affiliated={jeiEligible} />
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {jeiEligible
              ? 'Personnel R&D éligible à l’exonération de cotisations patronales JEI.'
              : 'Non éligible au dispositif JEI (personnel non R&D).'}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

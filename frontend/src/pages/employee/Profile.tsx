import { useAuth } from '@/contexts/AuthContext';
import { EmployeeProfileBankCard } from '@/components/employee-profile/EmployeeProfileBankCard';
import { EmployeeProfileContactCard } from '@/components/employee-profile/EmployeeProfileContactCard';
import { EmployeeProfileContractCard } from '@/components/employee-profile/EmployeeProfileContractCard';
import { EmployeePageShell } from '@/components/employee/EmployeePageHeader';
import { EmployeeProfileHeader } from '@/components/employee-profile/EmployeeProfileHeader';
import { EmployeeProfileIdentityBanner } from '@/components/employee-profile/EmployeeProfileIdentityBanner';
import { EmployeeProfilePayBenefitsGrid } from '@/components/employee-profile/EmployeeProfilePayBenefitsGrid';
import { WorkMedalEmployeeAction } from '@/features/work-medals/components/WorkMedalEmployeeAction';
import { EmployeeProfilePageSkeleton } from '@/components/skeletons/EmployeeProfilePageSkeleton';
import { useEmployeeProfilePageQuery } from '@/hooks/queries/useEmployeeDashboardQueries';
import { isProfileNotFoundError } from '@/lib/employeeProfileUtils';

export default function ProfilePage() {
  const { user } = useAuth();
  const userId = user?.id;
  const profileQuery = useEmployeeProfilePageQuery(userId);

  if (!userId) {
    return (
      <p className="text-sm text-muted-foreground">
        Connectez-vous pour accéder à votre profil.
      </p>
    );
  }

  if (profileQuery.isLoading) {
    return <EmployeeProfilePageSkeleton />;
  }

  const notConfigured =
    profileQuery.isError && isProfileNotFoundError(profileQuery.error);

  if (notConfigured) {
    return (
      <EmployeePageShell>
        <EmployeeProfileHeader />
        <div className="rounded-md border border-amber-200 bg-amber-50/50 p-4 text-sm text-amber-950">
          <p className="font-medium">Profil non relié</p>
          <p className="text-muted-foreground">
            Aucune fiche collaborateur n&apos;est associée à votre compte pour cette
            entreprise. Contactez les RH pour consulter vos informations.
          </p>
        </div>
      </EmployeePageShell>
    );
  }

  if (profileQuery.isError || !profileQuery.data) {
    return (
      <EmployeePageShell>
        <EmployeeProfileHeader />
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm">
          <p className="font-medium">Impossible de charger le profil</p>
          <p className="text-muted-foreground">
            Réessayez plus tard ou contactez votre service RH si le problème persiste.
          </p>
        </div>
      </EmployeePageShell>
    );
  }

  const profile = profileQuery.data;

  return (
    <EmployeePageShell>
      <EmployeeProfileHeader />
      <EmployeeProfileIdentityBanner profile={profile} />
      <EmployeeProfileContractCard profile={profile} />
      <EmployeeProfileContactCard profile={profile} />
      <EmployeeProfilePayBenefitsGrid profile={profile} />
      <WorkMedalEmployeeAction employeeId={profile.id} />
      <EmployeeProfileBankCard profile={profile} />
    </EmployeePageShell>
  );
}

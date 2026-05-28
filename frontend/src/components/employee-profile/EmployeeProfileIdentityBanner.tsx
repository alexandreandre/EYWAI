import type { EmployeeProfileData } from '@/lib/employeeProfileUtils';

interface EmployeeProfileIdentityBannerProps {
  profile: EmployeeProfileData;
}

export function EmployeeProfileIdentityBanner({ profile }: EmployeeProfileIdentityBannerProps) {
  const fullName = `${profile.first_name} ${profile.last_name}`.trim();

  return (
    <div className="rounded-lg border bg-muted/30 px-4 py-3">
      <p className="text-lg font-semibold">{fullName || 'Collaborateur'}</p>
      {profile.job_title ? (
        <p className="text-sm text-muted-foreground">{profile.job_title}</p>
      ) : null}
    </div>
  );
}

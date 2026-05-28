import { EmployeePageHeader } from '@/components/employee/EmployeePageHeader';

export function EmployeeProfileHeader() {
  return (
    <>
      <EmployeePageHeader
        title="Mon Profil"
        description="Vos informations personnelles et contractuelles."
      />
      <p className="rounded-md border border-muted bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
        Pour modifier vos coordonnées, contactez votre service RH.
      </p>
    </>
  );
}

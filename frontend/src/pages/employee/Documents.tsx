import {
  EmployeePageHeader,
  EmployeePageShell,
} from '@/components/employee/EmployeePageHeader';
import { EmployeeDocumentsFolderExplorer } from '@/components/documents/EmployeeDocumentsFolderExplorer';
import { EmployeeSelfDocumentsFolderContent } from '@/components/documents/EmployeeSelfDocumentsFolderContent';
import { useEmployeeSelfDocuments } from '@/hooks/useEmployeeSelfDocuments';
import { Skeleton } from '@/components/ui/skeleton';

export default function EmployeeDocumentsPage() {
  const data = useEmployeeSelfDocuments();
  const { notConfigured, isLoading, folderCounts, employee } = data;

  return (
    <EmployeePageShell>
      <EmployeePageHeader
        title="Documents"
        description="Vos contrats, pièces d'identité, bulletins et documents transmis par les RH."
      />

      {notConfigured && (
        <div className="rounded-md border border-amber-200 bg-amber-50/50 p-4 text-sm text-amber-950">
          <p className="font-medium">Profil non relié</p>
          <p className="text-muted-foreground">
            Aucune fiche collaborateur n&apos;est associée à votre compte pour cette entreprise.
            Contactez les RH pour consulter vos documents.
          </p>
        </div>
      )}

      {!notConfigured && isLoading && !employee && (
        <div className="space-y-2">
          <Skeleton className="h-[320px] w-full" />
        </div>
      )}

      {!notConfigured && employee && (
        <EmployeeDocumentsFolderExplorer
          folderCounts={folderCounts}
          renderFolderContent={(folderId, fileSearch) => (
            <EmployeeSelfDocumentsFolderContent
              data={data}
              folderId={folderId}
              fileSearch={fileSearch}
            />
          )}
        />
      )}
    </EmployeePageShell>
  );
}

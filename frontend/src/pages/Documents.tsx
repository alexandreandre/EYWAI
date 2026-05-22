import { CompanyDocumentsExplorer } from '@/components/documents/CompanyDocumentsExplorer';
import { useCompanyDocumentGeneration } from '@/components/documents/useCompanyDocumentGeneration';
import { EmployeeDocumentAddMenu } from '@/components/employee-detail/EmployeeDetailDocumentsRhSection';

export default function DocumentsRhPage() {
  const { handlers, dialogs, eywaiBanner, onManageTemplates } = useCompanyDocumentGeneration();

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
        <p className="text-sm text-muted-foreground">
          Tous les documents des collaborateurs — contrats, pièces d&apos;identité, bulletins et
          documents générés.
        </p>
      </div>

      {eywaiBanner && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          Dernier document généré avec le <strong>modèle standard EYWAI</strong>.
        </div>
      )}

      {dialogs}

      <CompanyDocumentsExplorer
        generatedHandlers={handlers}
        headerActions={
          <EmployeeDocumentAddMenu
            handlers={handlers}
            onManageTemplates={onManageTemplates}
            menuAlign="end"
          />
        }
      />
    </div>
  );
}

import { AdminPageHeader } from '@/features/admin/components/eywai/AdminPageHeader';
import { DsnImportWizard } from '@/features/dsn-import/components/DsnImportWizard';

export default function DsnImport() {
  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Import DSN"
        description="Reconstruisez un dossier paie complet (groupe, établissements, salariés, conventions et cumuls) à partir de fichiers DSN."
      />
      <DsnImportWizard />
    </div>
  );
}

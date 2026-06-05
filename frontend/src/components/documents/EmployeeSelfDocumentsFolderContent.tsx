import { useMemo, type ReactNode } from 'react';
import { DOCUMENT_TYPE_LABELS } from '@/api/documentLibrary';
import type { GeneratedDocument } from '@/api/documents';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { matchesFileSemantic } from '@/components/documents/companyDocumentsExplorerUtils';
import { EmployeeSelfGeneratedDocActions } from '@/components/documents/EmployeeSelfGeneratedDocActions';
import type { EmployeeSelfDocumentsData } from '@/hooks/useEmployeeSelfDocuments';
import {
  DOCUMENT_FOLDERS,
  groupPayslipsByYear,
  payslipLabel,
  type DocumentFolderId,
  type PayslipItem,
} from '@/components/employee-detail/employeeDetailDocumentsFolders';
import { DocumentFileRow, DownloadLinkButton, ViewLinkButton } from '@/components/employee-detail/DocumentFileRow';
import { GeneratedDocMeta } from '@/components/employee-detail/EmployeeDetailDocumentsRhSection';
import { RefreshCw } from 'lucide-react';

function FileListSkeleton() {
  return (
    <div className="space-y-2 p-2">
      <Skeleton className="h-14 w-full" />
      <Skeleton className="h-14 w-full" />
    </div>
  );
}

function ErrorRetry({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="p-4 text-center">
      <p className="text-sm text-muted-foreground mb-2">Erreur de chargement.</p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        <RefreshCw className="mr-2 h-3 w-3" />
        Réessayer
      </Button>
    </div>
  );
}

function filterGeneratedDocs(docs: GeneratedDocument[], fileSearch: string): GeneratedDocument[] {
  return docs.filter((d) =>
    matchesFileSemantic(
      [
        DOCUMENT_TYPE_LABELS[d.document_type] ?? d.document_type,
        d.document_type,
        d.file_name ?? '',
        d.status,
        d.template_name ?? '',
        d.is_eywai_template ? 'eywai standard' : 'personnalise',
      ],
      fileSearch
    )
  );
}

function filterPayslips(payslips: PayslipItem[], fileSearch: string): PayslipItem[] {
  return payslips.filter((p) =>
    matchesFileSemantic(
      [payslipLabel(p), p.name, String(p.month), String(p.year), 'bulletin paie'],
      fileSearch
    )
  );
}

export interface EmployeeSelfDocumentsFolderContentProps {
  data: EmployeeSelfDocumentsData;
  folderId: DocumentFolderId;
  fileSearch: string;
}

export function EmployeeSelfDocumentsFolderContent({
  data,
  folderId,
  fileSearch,
}: EmployeeSelfDocumentsFolderContentProps) {
  const {
    profile,
    contractUrl,
    identityUrl,
    credentialsPdfUrl,
    payslips,
    generatedByFolder,
    exitDocuments,
    expenseReceipts,
    isLoading,
    queries,
  } = data;

  const firstName = profile?.first_name ?? '';
  const lastName = profile?.last_name ?? '';

  const identityLabel = profile?.is_subject_to_residence_permit
    ? 'Titre de séjour'
    : "Carte d'identité / Passeport";

  const identityEmptyMessage = profile?.is_subject_to_residence_permit
    ? 'Aucun titre de séjour trouvé.'
    : "Aucune pièce d'identité trouvée.";

  const payslipsByYear = useMemo(
    () => (payslips.length > 12 ? groupPayslipsByYear(payslips) : null),
    [payslips]
  );

  const renderGeneratedRow = (doc: GeneratedDocument) => {
    const typeLabel = DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type;
    return (
      <DocumentFileRow
        key={doc.id}
        name={typeLabel}
        subtitle={doc.file_name || undefined}
        meta={<GeneratedDocMeta doc={doc} />}
        actions={<EmployeeSelfGeneratedDocActions doc={doc} />}
      />
    );
  };

  const renderPayslipRow = (p: PayslipItem) => (
    <DocumentFileRow
      key={p.id}
      name={payslipLabel(p)}
      actions={
        <>
          <ViewLinkButton href={p.preview_url ?? ''} title="Visualiser le bulletin" />
          <DownloadLinkButton href={p.url} download={p.name} />
        </>
      }
    />
  );

  const renderContrat = () => {
    const loading = isLoading || queries.contract.isLoading || queries.generated.isLoading;
    if (loading) return <FileListSkeleton />;
    if (queries.contract.isError || queries.generated.isError) {
      return (
        <ErrorRetry
          onRetry={() => {
            void queries.contract.refetch();
            void queries.generated.refetch();
          }}
        />
      );
    }

    const docs = filterGeneratedDocs(generatedByFolder.contrat, fileSearch);
    const items: ReactNode[] = [];

    if (
      contractUrl &&
      matchesFileSemantic(['contrat travail', 'contrat embauche', 'fichier signe'], fileSearch)
    ) {
      items.push(
        <DocumentFileRow
          key="uploaded-contract"
          name="Contrat de travail (fichier signé)"
          subtitle="Document importé à l’embauche"
          actions={
            <DownloadLinkButton
              href={contractUrl}
              download={`Contrat_${firstName}_${lastName}.pdf`}
            />
          }
        />
      );
    }

    for (const doc of docs) {
      items.push(renderGeneratedRow(doc));
    }

    if (items.length === 0) {
      const hasData =
        contractUrl || generatedByFolder.contrat.length > 0;
      return (
        <p className="py-8 text-center text-sm text-muted-foreground">
          {fileSearch.trim() && hasData
            ? 'Aucun fichier ne correspond à votre recherche.'
            : DOCUMENT_FOLDERS.find((f) => f.id === 'contrat')?.emptyMessage}
        </p>
      );
    }

    return <ul className="divide-y divide-border/60">{items}</ul>;
  };

  const renderIdentite = () => {
    if (isLoading || queries.identity.isLoading) return <FileListSkeleton />;
    if (queries.identity.isError) {
      return <ErrorRetry onRetry={() => void queries.identity.refetch()} />;
    }
    if (!identityUrl) {
      return (
        <p className="py-8 text-center text-sm text-muted-foreground">{identityEmptyMessage}</p>
      );
    }

    if (
      !matchesFileSemantic(
        [identityLabel, 'identite', 'passeport', 'titre sejour', 'piece identite'],
        fileSearch
      )
    ) {
      return (
        <p className="py-8 text-center text-sm text-muted-foreground">
          Aucun fichier ne correspond à votre recherche.
        </p>
      );
    }

    const subtitleParts: string[] = [];
    if (profile?.is_subject_to_residence_permit && profile.residence_permit_type) {
      let line = `Type : ${profile.residence_permit_type}`;
      if (profile.residence_permit_number) line += ` • N° ${profile.residence_permit_number}`;
      subtitleParts.push(line);
    }
    if (profile?.is_subject_to_residence_permit && profile.residence_permit_expiry_date) {
      subtitleParts.push(
        `Expire le ${new Date(profile.residence_permit_expiry_date).toLocaleDateString('fr-FR')}`
      );
    }

    return (
      <ul>
        <DocumentFileRow
          name={identityLabel}
          subtitle={subtitleParts.length > 0 ? subtitleParts.join(' — ') : undefined}
          actions={
            <DownloadLinkButton
              href={identityUrl}
              download={`${profile?.is_subject_to_residence_permit ? 'Titre_sejour' : 'Piece_identite'}_${firstName}_${lastName}`}
            />
          }
        />
      </ul>
    );
  };

  const renderBulletins = () => {
    if (isLoading || queries.payslips.isLoading) return <FileListSkeleton />;
    if (queries.payslips.isError) {
      return <ErrorRetry onRetry={() => void queries.payslips.refetch()} />;
    }

    const filtered = filterPayslips(payslips, fileSearch);
    if (payslips.length === 0) {
      return (
        <p className="py-8 text-center text-sm text-muted-foreground">
          {DOCUMENT_FOLDERS.find((f) => f.id === 'bulletins')?.emptyMessage}
        </p>
      );
    }
    if (filtered.length === 0) {
      return (
        <p className="py-8 text-center text-sm text-muted-foreground">
          Aucun fichier ne correspond à votre recherche.
        </p>
      );
    }

    if (payslipsByYear) {
      const yearBlocks = [...payslipsByYear.entries()]
        .map(([year, list]) => [year, filterPayslips(list, fileSearch)] as const)
        .filter(([, list]) => list.length > 0);
      if (yearBlocks.length === 0) {
        return (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Aucun fichier ne correspond à votre recherche.
          </p>
        );
      }
      return (
        <ul className="space-y-4">
          {yearBlocks.map(([year, list]) => (
            <li key={year}>
              <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {year}
              </p>
              <ul className="divide-y divide-border/60">{list.map(renderPayslipRow)}</ul>
            </li>
          ))}
        </ul>
      );
    }

    return <ul className="divide-y divide-border/60">{filtered.map(renderPayslipRow)}</ul>;
  };

  const renderAutres = () => {
    const loading =
      isLoading ||
      queries.generated.isLoading ||
      queries.exit.isLoading ||
      queries.expenses.isLoading ||
      queries.credentialsPdf.isLoading;
    if (loading) return <FileListSkeleton />;
    if (
      queries.generated.isError ||
      queries.exit.isError ||
      queries.expenses.isError ||
      queries.credentialsPdf.isError
    ) {
      return (
        <ErrorRetry
          onRetry={() => {
            void queries.generated.refetch();
            void queries.exit.refetch();
            void queries.expenses.refetch();
            void queries.credentialsPdf.refetch();
          }}
        />
      );
    }

    const items: ReactNode[] = [];

    if (
      credentialsPdfUrl &&
      matchesFileSemantic(['identifiants connexion', 'creation compte', 'compte'], fileSearch)
    ) {
      items.push(
        <DocumentFileRow
          key="credentials-pdf"
          name="Identifiants de connexion"
          subtitle="Identifiants de première connexion — modifiez votre mot de passe dès la première connexion"
          actions={
            <DownloadLinkButton
              href={credentialsPdfUrl}
              download={`Compte_${firstName}_${lastName}.pdf`}
            />
          }
        />
      );
    }

    for (const doc of filterGeneratedDocs(generatedByFolder.autres, fileSearch)) {
      items.push(renderGeneratedRow(doc));
    }

    for (const doc of exitDocuments) {
      if (!matchesFileSemantic([doc.name, 'document sortie', 'sortie'], fileSearch)) continue;
      items.push(
        <DocumentFileRow
          key={`exit-${doc.id}`}
          name={doc.name}
          subtitle={
            doc.date ? `Publié le ${new Date(doc.date).toLocaleDateString('fr-FR')}` : 'Document de sortie'
          }
          actions={<DownloadLinkButton href={doc.url} download={doc.name} />}
        />
      );
    }

    for (const receipt of expenseReceipts) {
      if (!matchesFileSemantic([receipt.name, receipt.subtitle, 'note de frais', 'justificatif'], fileSearch)) {
        continue;
      }
      items.push(
        <DocumentFileRow
          key={`expense-${receipt.id}`}
          name={receipt.name}
          subtitle={receipt.subtitle}
          actions={
            <DownloadLinkButton
              href={receipt.url}
              download={`${receipt.name.replace(/\s+/g, '_')}.pdf`}
            />
          }
        />
      );
    }

    if (items.length === 0) {
      const hasData =
        Boolean(credentialsPdfUrl) ||
        generatedByFolder.autres.length > 0 ||
        exitDocuments.length > 0 ||
        expenseReceipts.length > 0;
      return (
        <p className="py-8 text-center text-sm text-muted-foreground">
          {fileSearch.trim() && hasData
            ? 'Aucun fichier ne correspond à votre recherche.'
            : DOCUMENT_FOLDERS.find((f) => f.id === 'autres')?.emptyMessage}
        </p>
      );
    }

    return <ul className="divide-y divide-border/60">{items}</ul>;
  };

  switch (folderId) {
    case 'contrat':
      return renderContrat();
    case 'identite':
      return renderIdentite();
    case 'bulletins':
      return renderBulletins();
    case 'autres':
      return renderAutres();
    default:
      return null;
  }
}

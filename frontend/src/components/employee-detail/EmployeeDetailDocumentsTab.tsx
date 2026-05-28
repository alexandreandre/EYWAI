import { useMemo, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';
import { DOCUMENT_TYPE_LABELS } from '@/api/documentLibrary';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Edit, RefreshCw } from 'lucide-react';
import {
  DOCUMENT_FOLDERS,
  type DocumentFolderId,
  groupGeneratedByFolder,
  groupPayslipsByYear,
  payslipLabel,
  sortPayslipsDesc,
  type PayslipItem,
} from '@/components/employee-detail/employeeDetailDocumentsFolders';
import { DocumentFileRow, DownloadLinkButton } from '@/components/employee-detail/DocumentFileRow';
import {
  EmployeeDocumentAddMenu,
  GeneratedDocActions,
  GeneratedDocMeta,
  useEmployeeDocumentGeneration,
  type EmployeeDetailDocumentsRhEmployee,
} from '@/components/employee-detail/EmployeeDetailDocumentsRhSection';
import { EmployeeDocumentsFolderExplorer } from '@/components/documents/EmployeeDocumentsFolderExplorer';
import { countRhDetailFolderItems } from '@/components/documents/employeeDocumentsFolderCounts';
import { matchesFileSemantic } from '@/components/documents/companyDocumentsExplorerUtils';
import type { GeneratedDocument } from '@/api/documents';

interface ContractUrlResponse {
  url: string | null;
}

export interface EmployeeDetailDocumentsTabProps {
  employeeId: string;
  employee: EmployeeDetailDocumentsRhEmployee;
  credentialsPdfUrl?: string | null;
}

function FileListSkeleton() {
  return (
    <div className="space-y-2 p-2">
      <Skeleton className="h-14 w-full" />
      <Skeleton className="h-14 w-full" />
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

export function EmployeeDetailDocumentsTab({
  employeeId,
  employee,
  credentialsPdfUrl = null,
}: EmployeeDetailDocumentsTabProps) {
  const navigate = useNavigate();

  const {
    rows: generatedRows,
    isLoading: generatedLoading,
    isError: generatedError,
    refetch: refetchGenerated,
    eywaiBanner,
    handlers,
    dialogs,
  } = useEmployeeDocumentGeneration(employeeId, employee);

  const contractQuery = useQuery({
    queryKey: ['employee', employeeId, 'contract-url'],
    queryFn: async () => {
      const res = await apiClient.get<ContractUrlResponse>(`/api/employees/${employeeId}/contract`);
      return res.data.url ?? null;
    },
  });

  const identityQuery = useQuery({
    queryKey: ['employee', employeeId, 'identity-document-url'],
    queryFn: async () => {
      const res = await apiClient.get<ContractUrlResponse>(
        `/api/employees/${employeeId}/identity-document`
      );
      return res.data.url ?? null;
    },
  });

  const payslipsQuery = useQuery({
    queryKey: ['employee', employeeId, 'payslips'],
    queryFn: async () => {
      const res = await apiClient.get<PayslipItem[]>(`/api/employees/${employeeId}/payslips`);
      return sortPayslipsDesc(res.data ?? []);
    },
  });

  const contractUrl = contractQuery.data ?? null;
  const identityUrl = identityQuery.data ?? null;
  const payslips = payslipsQuery.data ?? [];

  const generatedByFolder = useMemo(() => groupGeneratedByFolder(generatedRows), [generatedRows]);

  const folderCounts = useMemo(() => {
    const opts = { contractUrl, identityUrl, payslips, credentialsPdfUrl, generatedByFolder };
    return Object.fromEntries(
      DOCUMENT_FOLDERS.map((f) => [f.id, countRhDetailFolderItems(f.id, opts)])
    ) as Record<DocumentFolderId, number>;
  }, [contractUrl, identityUrl, payslips, credentialsPdfUrl, generatedByFolder]);

  const payslipsByYear = useMemo(
    () => (payslips.length > 12 ? groupPayslipsByYear(payslips) : null),
    [payslips]
  );

  const identityLabel = employee.is_subject_to_residence_permit
    ? 'Titre de séjour'
    : "Carte d'identité / Passeport";

  const identityEmptyMessage = employee.is_subject_to_residence_permit
    ? 'Aucun titre de séjour trouvé.'
    : "Aucune pièce d'identité trouvée.";

  const renderGeneratedRow = (doc: GeneratedDocument) => {
    const typeLabel = DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type;
    return (
      <DocumentFileRow
        key={doc.id}
        name={typeLabel}
        subtitle={doc.file_name || undefined}
        meta={<GeneratedDocMeta doc={doc} />}
        actions={<GeneratedDocActions doc={doc} handlers={handlers} />}
      />
    );
  };

  const renderContratFiles = (fileSearch: string) => {
    const loading = contractQuery.isLoading || generatedLoading;
    if (loading) return <FileListSkeleton />;
    if (contractQuery.isError || generatedError) {
      return (
        <div className="p-4 text-center">
          <p className="text-sm text-muted-foreground mb-2">Erreur de chargement.</p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              void contractQuery.refetch();
              void refetchGenerated();
            }}
          >
            <RefreshCw className="mr-2 h-3 w-3" />
            Réessayer
          </Button>
        </div>
      );
    }

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
              download={`Contrat_${employee.first_name}_${employee.last_name}.pdf`}
            />
          }
        />
      );
    }

    for (const doc of filterGeneratedDocs(generatedByFolder.contrat, fileSearch)) {
      items.push(renderGeneratedRow(doc));
    }

    if (items.length === 0) {
      const hasData = contractUrl || generatedByFolder.contrat.length > 0;
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

  const renderIdentiteFiles = (fileSearch: string) => {
    if (identityQuery.isLoading) return <FileListSkeleton />;
    if (identityQuery.isError) {
      return (
        <div className="p-4 text-center">
          <Button variant="outline" size="sm" onClick={() => void identityQuery.refetch()}>
            Réessayer
          </Button>
        </div>
      );
    }
    if (!identityUrl) {
      return <p className="py-8 text-center text-sm text-muted-foreground">{identityEmptyMessage}</p>;
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
    if (employee.is_subject_to_residence_permit && employee.residence_permit_type) {
      let line = `Type : ${employee.residence_permit_type}`;
      if (employee.residence_permit_number) line += ` • N° ${employee.residence_permit_number}`;
      subtitleParts.push(line);
    }
    if (employee.is_subject_to_residence_permit && employee.residence_permit_expiry_date) {
      subtitleParts.push(
        `Expire le ${new Date(employee.residence_permit_expiry_date).toLocaleDateString('fr-FR')}`
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
              download={`${employee.is_subject_to_residence_permit ? 'Titre_sejour' : 'Piece_identite'}_${employee.first_name}_${employee.last_name}`}
            />
          }
        />
      </ul>
    );
  };

  const renderPayslipRow = (p: PayslipItem) => (
    <DocumentFileRow
      key={p.id}
      name={payslipLabel(p)}
      actions={
        <>
          <Button variant="outline" size="sm" asChild>
            <Link to={`/payslips/${p.id}/edit`}>
              <Edit className="mr-2 h-4 w-4" />
              Modifier
            </Link>
          </Button>
          <DownloadLinkButton href={p.url} download={p.name} />
        </>
      }
    />
  );

  const renderBulletinsFiles = (fileSearch: string) => {
    if (payslipsQuery.isLoading) return <FileListSkeleton />;
    if (payslipsQuery.isError) {
      return (
        <div className="p-4 text-center">
          <Button variant="outline" size="sm" onClick={() => void payslipsQuery.refetch()}>
            Réessayer
          </Button>
        </div>
      );
    }
    if (payslips.length === 0) {
      return (
        <p className="py-8 text-center text-sm text-muted-foreground">
          {DOCUMENT_FOLDERS.find((f) => f.id === 'bulletins')?.emptyMessage}
        </p>
      );
    }

    const filtered = filterPayslips(payslips, fileSearch);
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

  const renderAutresFiles = (fileSearch: string) => {
    if (generatedLoading) return <FileListSkeleton />;
    if (generatedError) {
      return (
        <div className="p-4 text-center">
          <Button variant="outline" size="sm" onClick={() => void refetchGenerated()}>
            Réessayer
          </Button>
        </div>
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
          subtitle="PDF de création de compte"
          actions={
            <DownloadLinkButton
              href={credentialsPdfUrl}
              download={`Compte_${employee.first_name}_${employee.last_name}.pdf`}
            />
          }
        />
      );
    }

    for (const doc of filterGeneratedDocs(generatedByFolder.autres, fileSearch)) {
      items.push(renderGeneratedRow(doc));
    }

    if (items.length === 0) {
      const hasData =
        Boolean(credentialsPdfUrl) || generatedByFolder.autres.length > 0;
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

  const renderFolderContent = (folderId: DocumentFolderId, fileSearch: string) => {
    switch (folderId) {
      case 'contrat':
        return renderContratFiles(fileSearch);
      case 'identite':
        return renderIdentiteFiles(fileSearch);
      case 'bulletins':
        return renderBulletinsFiles(fileSearch);
      case 'autres':
        return renderAutresFiles(fileSearch);
      default:
        return null;
    }
  };

  const manageTemplates = () => navigate('/company#bibliotheque');

  return (
    <div className="space-y-4">
      {eywaiBanner && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950">
          Dernier document généré avec le modèle standard EYWAI.
        </div>
      )}

      {dialogs}

      <EmployeeDocumentsFolderExplorer
        folderCounts={folderCounts}
        renderFolderContent={renderFolderContent}
        headerActions={
          <EmployeeDocumentAddMenu
            handlers={handlers}
            onManageTemplates={manageTemplates}
            menuAlign="end"
          />
        }
      />
    </div>
  );
}

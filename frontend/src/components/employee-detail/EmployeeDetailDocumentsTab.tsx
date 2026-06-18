import { useMemo, useRef, useState, type ReactNode } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';
import { uploadEmployeeContract } from '@/api/employees';
import { getGeneratedDocumentLabel } from '@/lib/generatedDocumentLabel';
import {
  hasNetSuperieurBrutWarning,
  isNetSuperieurBrutWarning,
  PayslipNetBrutInlineLabel,
} from '@/lib/payslipNetBrutAlert';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/components/ui/use-toast';
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
import { DocumentFileRow, DocumentPreviewDownloadActions, DownloadLinkButton, ViewLinkButton } from '@/components/employee-detail/DocumentFileRow';
import { EmployeeContractSetupPanel } from '@/components/employee-detail/EmployeeContractSetupPanel';
import {
  EmployeeDocumentAddMenu,
  GeneratedDocActions,
  GeneratedDocMeta,
  QK_EMPLOYEE_GENERATED_DOCS,
  useEmployeeDocumentGeneration,
  type EmployeeDetailDocumentsRhEmployee,
} from '@/components/employee-detail/EmployeeDetailDocumentsRhSection';
import { TransmitEmployeeDocumentDialog } from '@/components/employee-detail/TransmitEmployeeDocumentDialog';
import { getMissingContractGenerationFields } from '@/lib/employeeContractSetup';
import { EmployeeDocumentsFolderExplorer } from '@/components/documents/EmployeeDocumentsFolderExplorer';
import { countRhDetailFolderItems } from '@/components/documents/employeeDocumentsFolderCounts';
import { matchesFileSemantic } from '@/components/documents/companyDocumentsExplorerUtils';
import type { GeneratedDocument } from '@/api/documents';
import { rhEmployeeDocumentsAccessMessage } from '@/lib/employeeExitDocumentsAccess';
import { parseEmployeeDocumentDeepLink } from '@/lib/documentGenerationConfig';

interface ContractUrlResponse {
  url: string | null;
  preview_url?: string | null;
}

export interface EmployeeDetailDocumentsTabProps {
  employeeId: string;
  employee: EmployeeDetailDocumentsRhEmployee;
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
        getGeneratedDocumentLabel(d),
        d.document_type,
        d.file_name ?? '',
        d.status,
        d.template_name ?? '',
        String(d.generation_context?.custom_label ?? ''),
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
}: EmployeeDetailDocumentsTabProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const contractUploadInputRef = useRef<HTMLInputElement>(null);
  const [transmitDialogOpen, setTransmitDialogOpen] = useState(false);
  const employeeDisplayName = `${employee.first_name} ${employee.last_name}`.trim();

  const missingContractFields = useMemo(
    () => getMissingContractGenerationFields(employee),
    [employee],
  );

  const uploadContractMut = useMutation({
    mutationFn: (file: File) => uploadEmployeeContract(employeeId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employee', employeeId, 'contract-url'] });
      toast({ title: 'Contrat enregistré', description: 'Le PDF a été ajouté au dossier.' });
    },
    onError: (error: unknown) => {
      const msg =
        error && typeof error === 'object' && 'response' in error
          ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: 'Import impossible',
        description: typeof msg === 'string' ? msg : 'Impossible d’enregistrer le contrat.',
        variant: 'destructive',
      });
    },
  });

  const handleContractUpload = (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      toast({
        title: 'Format non supporté',
        description: 'Seuls les fichiers PDF sont acceptés.',
        variant: 'destructive',
      });
      return;
    }
    uploadContractMut.mutate(file);
  };

  const openContractUploadPicker = () => {
    contractUploadInputRef.current?.click();
  };

  const credentialsPdfQuery = useQuery({
    queryKey: ['employee', employeeId, 'credentials-pdf'],
    queryFn: async () => {
      const res = await apiClient.get<ContractUrlResponse>(
        `/api/employees/${employeeId}/credentials-pdf`,
      );
      return {
        downloadUrl: res.data.url ?? null,
        previewUrl: res.data.preview_url ?? res.data.url ?? null,
      };
    },
    enabled: Boolean(employeeId),
    retry: false,
    staleTime: 5 * 60_000,
  });
  const credentialsPdfUrl = credentialsPdfQuery.data?.downloadUrl ?? null;
  const credentialsPdfPreviewUrl = credentialsPdfQuery.data?.previewUrl ?? null;

  const deepLink = useMemo(
    () => parseEmployeeDocumentDeepLink(searchParams.toString()),
    [searchParams]
  );

  const {
    rows: generatedRows,
    isLoading: generatedLoading,
    isError: generatedError,
    refetch: refetchGenerated,
    eywaiBanner,
    handlers,
    dialogs,
  } = useEmployeeDocumentGeneration(
    employeeId,
    employee,
    deepLink.generate ? deepLink : undefined
  );

  const contractQuery = useQuery({
    queryKey: ['employee', employeeId, 'contract-url'],
    queryFn: async () => {
      const res = await apiClient.get<ContractUrlResponse>(`/api/employees/${employeeId}/contract`);
      return {
        downloadUrl: res.data.url ?? null,
        previewUrl: res.data.preview_url ?? res.data.url ?? null,
      };
    },
  });

  const identityQuery = useQuery({
    queryKey: ['employee', employeeId, 'identity-document-url'],
    queryFn: async () => {
      const res = await apiClient.get<ContractUrlResponse>(
        `/api/employees/${employeeId}/identity-document`
      );
      return {
        downloadUrl: res.data.url ?? null,
        previewUrl: res.data.preview_url ?? res.data.url ?? null,
      };
    },
  });

  const payslipsQuery = useQuery({
    queryKey: ['employee', employeeId, 'payslips'],
    queryFn: async () => {
      const res = await apiClient.get<PayslipItem[]>(`/api/employees/${employeeId}/payslips`);
      return sortPayslipsDesc(res.data ?? []);
    },
  });

  const contractUrl = contractQuery.data?.downloadUrl ?? null;
  const contractPreviewUrl = contractQuery.data?.previewUrl ?? null;
  const identityUrl = identityQuery.data?.downloadUrl ?? null;
  const identityPreviewUrl = identityQuery.data?.previewUrl ?? null;
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

  const exitDocumentsMessage = useMemo(
    () => rhEmployeeDocumentsAccessMessage(employee),
    [employee],
  );

  const identityLabel = employee.is_subject_to_residence_permit
    ? 'Titre de séjour'
    : "Carte d'identité / Passeport";

  const identityEmptyMessage = employee.is_subject_to_residence_permit
    ? 'Aucun titre de séjour trouvé.'
    : "Aucune pièce d'identité trouvée.";

  const renderGeneratedRow = (doc: GeneratedDocument) => {
    const typeLabel = getGeneratedDocumentLabel(doc);
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
            <DocumentPreviewDownloadActions
              previewUrl={contractPreviewUrl}
              downloadUrl={contractUrl}
              downloadName={`Contrat_${employee.first_name}_${employee.last_name}.pdf`}
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
      if (fileSearch.trim() && hasData) {
        return (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Aucun fichier ne correspond à votre recherche.
          </p>
        );
      }
      return (
        <EmployeeContractSetupPanel
          onUpload={handleContractUpload}
          onGenerate={handlers.openContrat}
          isUploading={uploadContractMut.isPending}
          missingFields={missingContractFields}
        />
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
            <DocumentPreviewDownloadActions
              previewUrl={identityPreviewUrl}
              downloadUrl={identityUrl}
              downloadName={`${employee.is_subject_to_residence_permit ? 'Titre_sejour' : 'Piece_identite'}_${employee.first_name}_${employee.last_name}`}
            />
          }
        />
      </ul>
    );
  };

  const renderPayslipRow = (p: PayslipItem) => {
    const warnings = p.warnings ?? [];
    const showNetBrut = hasNetSuperieurBrutWarning(warnings);
    const otherWarnings = warnings.filter((w) => !isNetSuperieurBrutWarning(w));
    const firstOtherWarning = otherWarnings[0];
    return (
      <DocumentFileRow
        key={p.id}
        name={
          <>
            {payslipLabel(p)}
            {showNetBrut ? <PayslipNetBrutInlineLabel /> : null}
          </>
        }
        rowHref={`/payslips/${p.id}/edit`}
        subtitle={
          firstOtherWarning ? (
            <span className="text-amber-700 dark:text-amber-400">{firstOtherWarning}</span>
          ) : undefined
        }
        meta={
          firstOtherWarning ? (
            <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-800">
              Alerte
            </Badge>
          ) : undefined
        }
        actions={
          <>
            <ViewLinkButton
              href={p.preview_url ?? p.url ?? ''}
              title="Visualiser le bulletin"
              downloadUrl={p.url}
              downloadName={p.name}
            />
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
  };

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
    if (generatedLoading || credentialsPdfQuery.isLoading) return <FileListSkeleton />;
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

    if (credentialsPdfQuery.isError) {
      items.push(
        <li key="credentials-pdf-error" className="px-3 py-4 text-center">
          <p className="mb-2 text-sm text-muted-foreground">
            Impossible de charger les identifiants de connexion.
          </p>
          <Button variant="outline" size="sm" onClick={() => void credentialsPdfQuery.refetch()}>
            Réessayer
          </Button>
        </li>,
      );
    } else if (
      credentialsPdfUrl &&
      matchesFileSemantic(['identifiants connexion', 'creation compte', 'compte'], fileSearch)
    ) {
      items.push(
        <DocumentFileRow
          key="credentials-pdf"
          name="Identifiants de connexion"
          subtitle="Identifiants de première connexion — mot de passe temporaire à modifier"
          actions={
            <DocumentPreviewDownloadActions
              previewUrl={credentialsPdfPreviewUrl}
              downloadUrl={credentialsPdfUrl}
              downloadName={`Compte_${employee.first_name}_${employee.last_name}.pdf`}
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

  const manageTemplates = () => navigate('/company?tab=modeles');

  return (
    <div className="space-y-4">
      <input
        ref={contractUploadInputRef}
        type="file"
        accept=".pdf,application/pdf"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) handleContractUpload(file);
          event.target.value = '';
        }}
      />

      {exitDocumentsMessage && (
        <div className="rounded-md border border-blue-200 bg-blue-50/70 px-3 py-2 text-sm text-blue-950">
          {exitDocumentsMessage}
        </div>
      )}

      {eywaiBanner && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950">
          Dernier document généré avec le modèle standard EYWAI.
        </div>
      )}

      {dialogs}

      <TransmitEmployeeDocumentDialog
        open={transmitDialogOpen}
        onOpenChange={setTransmitDialogOpen}
        employeeId={employeeId}
        employeeName={employeeDisplayName}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: QK_EMPLOYEE_GENERATED_DOCS(employeeId) });
        }}
      />

      <EmployeeDocumentsFolderExplorer
        key={employeeId}
        initialFolder="contrat"
        folderCounts={folderCounts}
        renderFolderContent={renderFolderContent}
        headerActions={
          <EmployeeDocumentAddMenu
            handlers={handlers}
            onManageTemplates={manageTemplates}
            onTransmitDocument={() => setTransmitDialogOpen(true)}
            onImportContract={openContractUploadPicker}
            menuAlign="end"
          />
        }
      />
    </div>
  );
}

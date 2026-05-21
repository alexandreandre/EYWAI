import { useMemo, useState, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';
import { DOCUMENT_TYPE_LABELS } from '@/api/documentLibrary';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { Edit, Folder, FolderOpen, RefreshCw } from 'lucide-react';
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

function countFolderItems(
  folderId: DocumentFolderId,
  opts: {
    contractUrl: string | null;
    identityUrl: string | null;
    payslips: PayslipItem[];
    credentialsPdfUrl: string | null;
    generatedByFolder: ReturnType<typeof groupGeneratedByFolder>;
  }
): number {
  switch (folderId) {
    case 'contrat':
      return (opts.contractUrl ? 1 : 0) + opts.generatedByFolder.contrat.length;
    case 'identite':
      return opts.identityUrl ? 1 : 0;
    case 'bulletins':
      return opts.payslips.length;
    case 'autres':
      return opts.generatedByFolder.autres.length + (opts.credentialsPdfUrl ? 1 : 0);
    default:
      return 0;
  }
}

export function EmployeeDetailDocumentsTab({
  employeeId,
  employee,
  credentialsPdfUrl = null,
}: EmployeeDetailDocumentsTabProps) {
  const navigate = useNavigate();
  const [selectedFolder, setSelectedFolder] = useState<DocumentFolderId>('contrat');
  const [mobileOpenFolder, setMobileOpenFolder] = useState<DocumentFolderId | null>('contrat');

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
      DOCUMENT_FOLDERS.map((f) => [f.id, countFolderItems(f.id, opts)])
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

  const renderContratFiles = () => {
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

    if (contractUrl) {
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

    for (const doc of generatedByFolder.contrat) {
      const typeLabel = DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type;
      items.push(
        <DocumentFileRow
          key={doc.id}
          name={typeLabel}
          subtitle={doc.file_name || undefined}
          meta={<GeneratedDocMeta doc={doc} />}
          actions={<GeneratedDocActions doc={doc} handlers={handlers} />}
        />
      );
    }

    if (items.length === 0) {
      return (
        <p className="py-8 text-center text-sm text-muted-foreground">
          {DOCUMENT_FOLDERS.find((f) => f.id === 'contrat')?.emptyMessage}
        </p>
      );
    }

    return <ul className="divide-y divide-border/60">{items}</ul>;
  };

  const renderIdentiteFiles = () => {
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

  const renderBulletinsFiles = () => {
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

    if (payslipsByYear) {
      return (
        <ul className="space-y-4">
          {[...payslipsByYear.entries()].map(([year, list]) => (
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

    return <ul className="divide-y divide-border/60">{payslips.map(renderPayslipRow)}</ul>;
  };

  const renderAutresFiles = () => {
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

    if (credentialsPdfUrl) {
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

    for (const doc of generatedByFolder.autres) {
      const typeLabel = DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type;
      items.push(
        <DocumentFileRow
          key={doc.id}
          name={typeLabel}
          subtitle={doc.file_name || undefined}
          meta={<GeneratedDocMeta doc={doc} />}
          actions={<GeneratedDocActions doc={doc} handlers={handlers} />}
        />
      );
    }

    if (items.length === 0) {
      return (
        <p className="py-8 text-center text-sm text-muted-foreground">
          {DOCUMENT_FOLDERS.find((f) => f.id === 'autres')?.emptyMessage}
        </p>
      );
    }

    return <ul className="divide-y divide-border/60">{items}</ul>;
  };

  const renderFolderContent = (folderId: DocumentFolderId) => {
    switch (folderId) {
      case 'contrat':
        return renderContratFiles();
      case 'identite':
        return renderIdentiteFiles();
      case 'bulletins':
        return renderBulletinsFiles();
      case 'autres':
        return renderAutresFiles();
      default:
        return null;
    }
  };

  const selectedMeta = DOCUMENT_FOLDERS.find((f) => f.id === selectedFolder)!;

  const renderFolderButton = (folder: (typeof DOCUMENT_FOLDERS)[number], variant: 'sidebar' | 'accordion') => {
    const count = folderCounts[folder.id];
    const isSelected = variant === 'sidebar' ? selectedFolder === folder.id : mobileOpenFolder === folder.id;
    const Icon = isSelected ? FolderOpen : Folder;

    const btn = (
      <button
        type="button"
        onClick={() => {
          if (variant === 'sidebar') {
            setSelectedFolder(folder.id);
          } else {
            setMobileOpenFolder((prev) => (prev === folder.id ? null : folder.id));
          }
        }}
        className={cn(
          'flex w-full items-center gap-2 rounded-md px-3 py-2.5 text-left text-sm transition-colors',
          isSelected
            ? 'bg-primary/10 text-primary font-medium'
            : 'text-foreground hover:bg-muted/80'
        )}
      >
        <Icon className="h-4 w-4 shrink-0 opacity-80" aria-hidden />
        <span className="min-w-0 flex-1 truncate">{folder.label}</span>
        <Badge variant="secondary" className="shrink-0 tabular-nums">
          {count}
        </Badge>
      </button>
    );

    return btn;
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

      {/* Desktop : explorateur deux colonnes */}
      <Card className="hidden lg:block overflow-hidden">
        <div className="grid min-h-[320px] grid-cols-[minmax(240px,280px)_1fr]">
          <div className="border-r bg-muted/30 p-3">
            <p className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Dossiers
            </p>
            <nav className="space-y-0.5" aria-label="Dossiers documents">
              {DOCUMENT_FOLDERS.map((folder) => (
                <div key={folder.id}>{renderFolderButton(folder, 'sidebar')}</div>
              ))}
            </nav>
          </div>
          <div className="flex flex-col">
            <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
              <div className="min-w-0">
                <h3 className="font-semibold leading-tight">{selectedMeta.label}</h3>
                <p className="text-xs text-muted-foreground">
                  {folderCounts[selectedFolder]} fichier
                  {folderCounts[selectedFolder] !== 1 ? 's' : ''}
                </p>
              </div>
              <EmployeeDocumentAddMenu
                handlers={handlers}
                onManageTemplates={manageTemplates}
                menuAlign={'end'}
              />
            </div>
            <div className="flex-1 overflow-y-auto p-2">{renderFolderContent(selectedFolder)}</div>
          </div>
        </div>
      </Card>

      {/* Mobile / tablette : accordéons empilés */}
      <div className="space-y-3 lg:hidden">
        {DOCUMENT_FOLDERS.map((folder) => {
          const isOpen = mobileOpenFolder === folder.id;
          return (
            <Card key={folder.id} className="overflow-hidden">
              <CardHeader className="py-3">
                <div className="flex items-start justify-between gap-2">
                  <button
                    type="button"
                    className="flex min-w-0 flex-1 items-center gap-2 text-left"
                    onClick={() =>
                      setMobileOpenFolder((prev) => (prev === folder.id ? null : folder.id))
                    }
                    aria-expanded={isOpen}
                  >
                    {isOpen ? (
                      <FolderOpen className="h-5 w-5 shrink-0 text-primary" />
                    ) : (
                      <Folder className="h-5 w-5 shrink-0 text-muted-foreground" />
                    )}
                    <div className="min-w-0">
                      <CardTitle className="text-base leading-snug">{folder.label}</CardTitle>
                      <CardDescription className="mt-0.5">
                        {folderCounts[folder.id]} fichier{folderCounts[folder.id] !== 1 ? 's' : ''}
                      </CardDescription>
                    </div>
                  </button>
                  <EmployeeDocumentAddMenu
                    handlers={handlers}
                    onManageTemplates={manageTemplates}
                    menuAlign={'end'}
                  />
                </div>
              </CardHeader>
              {isOpen && <CardContent className="pt-0 pb-4">{renderFolderContent(folder.id)}</CardContent>}
            </Card>
          );
        })}
      </div>
    </div>
  );
}

import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  getDocumentsExplorer,
  type GeneratedDocument,
  type ExplorerPayslipItem,
  type ExplorerStorageItem,
} from '@/api/documents';
import { DOCUMENT_TYPE_LABELS } from '@/api/documentLibrary';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  DOCUMENT_FOLDERS,
  type DocumentFolderId,
  groupGeneratedByFolder,
  payslipLabel,
  sortPayslipsDesc,
  type PayslipItem,
} from '@/components/employee-detail/employeeDetailDocumentsFolders';
import { DocumentFileRow, DocumentPreviewDownloadActions, DownloadLinkButton, ViewLinkButton } from '@/components/employee-detail/DocumentFileRow';
import {
  GeneratedDocActions,
  GeneratedDocMeta,
} from '@/components/employee-detail/EmployeeDetailDocumentsRhSection';
import {
  countFilesInEmployeeGroups,
  groupGeneratedByEmployee,
  groupPayslipsByEmployee,
  groupStorageByEmployee,
  matchesEmployeeSemantic,
  matchesFileSemantic,
  payslipsContentBlocks,
  sortEmployeeGroups,
  type EmployeeGroupMeta,
} from '@/components/documents/companyDocumentsExplorerUtils';
import { EmployeeDocumentSubfolder } from '@/components/documents/EmployeeDocumentSubfolder';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { queryKeys } from '@/lib/queryKeys';
import { Edit, Folder, FolderOpen, RefreshCw, Search, User } from 'lucide-react';

export const QK_COMPANY_DOCUMENTS_EXPLORER = ['company-documents-explorer'] as const;

function FileListSkeleton() {
  return (
    <div className="space-y-2 p-2">
      <Skeleton className="h-14 w-full" />
      <Skeleton className="h-14 w-full" />
    </div>
  );
}

function toPayslipItems(rows: ExplorerPayslipItem[]): PayslipItem[] {
  return rows.map((p) => ({
    id: p.id,
    name: p.name,
    url: p.url,
    preview_url: p.preview_url,
    month: p.month,
    year: p.year,
  }));
}

type FolderEmployeeEntry = EmployeeGroupMeta & { fileCount: number };

type EmployeeGroup = {
  meta: EmployeeGroupMeta;
  docs?: GeneratedDocument[];
  items?: ExplorerStorageItem[];
  payslips?: PayslipItem[];
};

export interface CompanyDocumentsExplorerProps {
  generatedHandlers: React.ComponentProps<typeof GeneratedDocActions>['handlers'];
  headerActions?: ReactNode;
}

export function CompanyDocumentsExplorer({
  generatedHandlers,
  headerActions,
}: CompanyDocumentsExplorerProps) {
  const companyId = useActiveCompanyId();
  const [selectedFolder, setSelectedFolder] = useState<DocumentFolderId>('contrat');
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | null>(null);
  const [mobileOpenFolder, setMobileOpenFolder] = useState<DocumentFolderId | null>('contrat');
  const [mobileOpenEmployees, setMobileOpenEmployees] = useState<Set<string>>(new Set());
  const [employeeSearch, setEmployeeSearch] = useState('');
  const [fileSearch, setFileSearch] = useState('');

  const explorerQuery = useQuery({
    queryKey: queryKeys.documentsExplorer(companyId),
    queryFn: getDocumentsExplorer,
    enabled: Boolean(companyId),
    refetchOnMount: 'always',
  });

  const generatedRows = useMemo(
    () => explorerQuery.data?.generated ?? [],
    [explorerQuery.data?.generated]
  );
  const generatedByFolder = useMemo(() => groupGeneratedByFolder(generatedRows), [generatedRows]);

  const storageByKind = useMemo(() => {
    const storage = explorerQuery.data?.storage ?? [];
    return {
      contract: storage.filter((s) => s.kind === 'contract'),
      identity: storage.filter((s) => s.kind === 'identity'),
      credentials: storage.filter((s) => s.kind === 'credentials'),
    };
  }, [explorerQuery.data?.storage]);

  const payslipsAll = useMemo(
    () => sortPayslipsDesc(toPayslipItems(explorerQuery.data?.payslips ?? [])),
    [explorerQuery.data?.payslips]
  );

  const payslipsById = useMemo(() => {
    const map = new Map<string, ExplorerPayslipItem>();
    for (const p of explorerQuery.data?.payslips ?? []) {
      map.set(p.id, p);
    }
    return map;
  }, [explorerQuery.data?.payslips]);

  const folderData = useMemo(() => {
    const contratGen = groupGeneratedByEmployee(generatedByFolder.contrat);
    const autresGen = groupGeneratedByEmployee(generatedByFolder.autres);
    const contracts = groupStorageByEmployee(storageByKind.contract);
    const identities = groupStorageByEmployee(storageByKind.identity);
    const credentials = groupStorageByEmployee(storageByKind.credentials);
    const payslips = groupPayslipsByEmployee(payslipsAll, payslipsById);

    const contratMerged = mergeEmployeeGroups(contracts, contratGen);
    const autresMerged = mergeEmployeeGroups(credentials, autresGen);

    return {
      contrat: { groups: contratMerged, fileCount: countFilesInEmployeeGroups(contratMerged) },
      identite: { groups: identities, fileCount: countFilesInEmployeeGroups(identities) },
      bulletins: { groups: payslips, fileCount: countFilesInEmployeeGroups(payslips) },
      autres: { groups: autresMerged, fileCount: countFilesInEmployeeGroups(autresMerged) },
    } satisfies Record<DocumentFolderId, { groups: EmployeeGroup[]; fileCount: number }>;
  }, [generatedByFolder, storageByKind, payslipsAll, payslipsById]);

  const folderCounts = useMemo(
    () =>
      Object.fromEntries(
        DOCUMENT_FOLDERS.map((f) => [f.id, folderData[f.id].fileCount])
      ) as Record<DocumentFolderId, number>,
    [folderData]
  );

  const currentFolder = folderData[selectedFolder];

  const allEmployeeEntries: FolderEmployeeEntry[] = useMemo(
    () =>
      currentFolder.groups.map((g) => ({
        ...g.meta,
        fileCount:
          (g.docs?.length ?? 0) + (g.items?.length ?? 0) + (g.payslips?.length ?? 0),
      })),
    [currentFolder.groups]
  );

  const filteredEmployeeEntries = useMemo(
    () =>
      allEmployeeEntries.filter((e) => matchesEmployeeSemantic(e.employeeName, employeeSearch)),
    [allEmployeeEntries, employeeSearch]
  );

  useEffect(() => {
    setSelectedEmployeeId((current) => {
      const ids = filteredEmployeeEntries.map((e) => e.employeeId);
      if (ids.length === 0) return null;
      if (current && ids.includes(current)) return current;
      return ids[0];
    });
  }, [selectedFolder, filteredEmployeeEntries]);

  useEffect(() => {
    setMobileOpenEmployees(new Set());
  }, [selectedFolder, employeeSearch]);

  useEffect(() => {
    setFileSearch('');
  }, [selectedFolder, selectedEmployeeId]);

  const selectedGroup = currentFolder.groups.find((g) => g.meta.employeeId === selectedEmployeeId);

  const renderGeneratedRow = (doc: GeneratedDocument) => {
    const typeLabel = DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type;
    return (
      <DocumentFileRow
        key={doc.id}
        name={typeLabel}
        subtitle={doc.file_name || undefined}
        meta={<GeneratedDocMeta doc={doc} />}
        actions={<GeneratedDocActions doc={doc} handlers={generatedHandlers} />}
      />
    );
  };

  const renderStorageRow = (item: ExplorerStorageItem) => {
    const downloadName =
      item.kind === 'contract'
        ? `Contrat_${item.employee_name.replace(/\s+/g, '_')}.pdf`
        : item.kind === 'credentials'
          ? `Compte_${item.employee_name.replace(/\s+/g, '_')}.pdf`
          : `Identite_${item.employee_name.replace(/\s+/g, '_')}`;

    const subtitle =
      item.kind === 'contract' ? "Document importé à l'embauche" : undefined;

    return (
      <DocumentFileRow
        key={`${item.kind}-${item.employee_id}`}
        name={item.label}
        subtitle={subtitle}
        actions={
          <DocumentPreviewDownloadActions
            previewUrl={item.preview_url}
            downloadUrl={item.url}
            downloadName={downloadName}
          />
        }
      />
    );
  };

  const renderPayslipRow = (p: PayslipItem) => (
    <DocumentFileRow
      key={p.id}
      name={payslipLabel(p)}
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

  const filterGroupFiles = (group: EmployeeGroup) => {
    const items = (group.items ?? []).filter((s) =>
      matchesFileSemantic(
        [
          s.label,
          s.kind === 'contract' ? 'contrat embauche' : s.kind === 'credentials' ? 'compte identifiants' : 'identite',
        ],
        fileSearch
      )
    );
    const docs = (group.docs ?? []).filter((d) =>
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
    const payslips = (group.payslips ?? []).filter((p) =>
      matchesFileSemantic(
        [payslipLabel(p), p.name, String(p.month), String(p.year), 'bulletin paie'],
        fileSearch
      )
    );
    return { items, docs, payslips };
  };

  const renderEmployeeFiles = (
    group: EmployeeGroup | undefined,
    options?: { showFileSearch?: boolean; searchIdSuffix?: string }
  ): ReactNode => {
    if (!group) {
      return (
        <p className="py-12 text-center text-sm text-muted-foreground">
          {employeeSearch.trim()
            ? 'Aucun collaborateur ne correspond à votre recherche.'
            : 'Sélectionnez un collaborateur dans la liste.'}
        </p>
      );
    }

    const totalCount =
      (group.items?.length ?? 0) + (group.docs?.length ?? 0) + (group.payslips?.length ?? 0);
    const { items: filteredItems, docs: filteredDocs, payslips: filteredPayslips } =
      filterGroupFiles(group);
    const visibleCount =
      filteredItems.length + filteredDocs.length + filteredPayslips.length;

    const fileList = () => {
      const rows: ReactNode[] = [];
      for (const s of filteredItems) {
        rows.push(renderStorageRow(s));
      }
      for (const doc of filteredDocs) {
        rows.push(renderGeneratedRow(doc));
      }

      if (filteredPayslips.length > 0) {
        const blocks = payslipsContentBlocks(filteredPayslips);
        if (blocks instanceof Map) {
          const yearBlocks = [...blocks.entries()].filter(([, list]) => list.length > 0);
          if (yearBlocks.length === 0) return null;
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
        return <ul className="divide-y divide-border/60">{filteredPayslips.map(renderPayslipRow)}</ul>;
      }

      if (rows.length === 0) return null;
      return <ul className="divide-y divide-border/60">{rows}</ul>;
    };

    const listContent = fileList();

    if (totalCount === 0) {
      return (
        <p className="py-8 text-center text-sm text-muted-foreground">Aucun fichier pour ce collaborateur.</p>
      );
    }

    if (!listContent) {
      return (
        <p className="py-8 text-center text-sm text-muted-foreground">
          Aucun fichier ne correspond à votre recherche.
        </p>
      );
    }

    const searchBlock =
      options?.showFileSearch !== false ? (
        <div className="space-y-1 pb-2">
          {fileSearchField(options?.searchIdSuffix ?? 'files')}
          {fileSearch.trim() && visibleCount < totalCount && (
            <p className="px-1 text-xs text-muted-foreground">
              {visibleCount} sur {totalCount} fichier{totalCount !== 1 ? 's' : ''} affiché
              {visibleCount !== 1 ? 's' : ''}
            </p>
          )}
        </div>
      ) : null;

    return (
      <div className="space-y-2">
        {searchBlock}
        {listContent}
      </div>
    );
  };

  const renderFolderEmpty = (folderId: DocumentFolderId) => (
    <p className="py-8 text-center text-sm text-muted-foreground">
      {DOCUMENT_FOLDERS.find((f) => f.id === folderId)?.emptyMessage}
    </p>
  );

  const renderLoadingOrError = () => {
    if (explorerQuery.isLoading) return <FileListSkeleton />;
    if (explorerQuery.isError) {
      return (
        <div className="p-4 text-center">
          <p className="text-sm text-muted-foreground mb-2">Erreur de chargement.</p>
          <Button variant="outline" size="sm" onClick={() => void explorerQuery.refetch()}>
            <RefreshCw className="mr-2 h-3 w-3" />
            Réessayer
          </Button>
        </div>
      );
    }
    return null;
  };

  const employeeSearchField = (idSuffix: string) => (
    <div className="relative">
      <Search
        className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
        aria-hidden
      />
      <Input
        id={`employee-doc-search-${idSuffix}`}
        type="search"
        placeholder="Rechercher un collaborateur…"
        value={employeeSearch}
        onChange={(e) => setEmployeeSearch(e.target.value)}
        className="h-8 pl-8 text-sm"
        aria-label="Rechercher parmi les collaborateurs"
      />
    </div>
  );

  const fileSearchField = (idSuffix: string) => (
    <div className="relative">
      <Search
        className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
        aria-hidden
      />
      <Input
        id={`file-doc-search-${idSuffix}`}
        type="search"
        placeholder="Rechercher un fichier…"
        value={fileSearch}
        onChange={(e) => setFileSearch(e.target.value)}
        className="h-8 pl-8 text-sm"
        aria-label="Rechercher parmi les fichiers"
      />
    </div>
  );

  const renderMobileFolderContent = (folderId: DocumentFolderId) => {
    const state = renderLoadingOrError();
    if (state) return state;

    const { groups } = folderData[folderId];
    if (groups.length === 0) return renderFolderEmpty(folderId);

    const visibleGroups = groups.filter((g) =>
      matchesEmployeeSemantic(g.meta.employeeName, employeeSearch)
    );

    return (
      <div className="space-y-3">
        {employeeSearchField(`mobile-${folderId}`)}
        {visibleGroups.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            Aucun collaborateur ne correspond à votre recherche.
          </p>
        ) : (
          <div className="space-y-2">
            {visibleGroups.map((group) => {
              const empId = group.meta.employeeId;
              const isOpen = mobileOpenEmployees.has(empId);
              const fileCount =
                (group.docs?.length ?? 0) + (group.items?.length ?? 0) + (group.payslips?.length ?? 0);
              return (
                <EmployeeDocumentSubfolder
                  key={empId}
                  meta={group.meta}
                  fileCount={fileCount}
                  isOpen={isOpen}
                  onToggle={() =>
                    setMobileOpenEmployees((prev) => {
                      const next = new Set(prev);
                      if (next.has(empId)) next.delete(empId);
                      else next.add(empId);
                      return next;
                    })
                  }
                >
                  {renderEmployeeFiles(group, {
                    searchIdSuffix: `mobile-${folderId}-${empId}`,
                  })}
                </EmployeeDocumentSubfolder>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  const selectedMeta = DOCUMENT_FOLDERS.find((f) => f.id === selectedFolder)!;
  const selectedEmployeeName =
    filteredEmployeeEntries.find((e) => e.employeeId === selectedEmployeeId)?.employeeName ?? '';

  const selectedFileStats = useMemo(() => {
    if (!selectedGroup) return { total: 0, visible: 0 };
    const total =
      (selectedGroup.items?.length ?? 0) +
      (selectedGroup.docs?.length ?? 0) +
      (selectedGroup.payslips?.length ?? 0);
    const { items, docs, payslips } = filterGroupFiles(selectedGroup);
    return {
      total,
      visible: items.length + docs.length + payslips.length,
    };
  }, [selectedGroup, fileSearch]);

  const renderFolderButton = (folder: (typeof DOCUMENT_FOLDERS)[number], variant: 'sidebar' | 'accordion') => {
    const count = folderCounts[folder.id];
    const employeeCount = folderData[folder.id].groups.length;
    const isSelected =
      variant === 'sidebar' ? selectedFolder === folder.id : mobileOpenFolder === folder.id;
    const Icon = isSelected ? FolderOpen : Folder;

    return (
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
        <span className="min-w-0 flex-1">
          <span className="block truncate">{folder.label}</span>
          {variant === 'sidebar' && employeeCount > 0 && (
            <span className="block truncate text-xs font-normal text-muted-foreground">
              {employeeCount} collaborateur{employeeCount !== 1 ? 's' : ''}
            </span>
          )}
        </span>
        <Badge variant="secondary" className="shrink-0 tabular-nums">
          {count}
        </Badge>
      </button>
    );
  };

  const renderEmployeeButton = (entry: FolderEmployeeEntry) => {
    const isSelected = selectedEmployeeId === entry.employeeId;
    return (
      <button
        key={entry.employeeId}
        type="button"
        onClick={() => setSelectedEmployeeId(entry.employeeId)}
        className={cn(
          'flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors',
          isSelected
            ? 'bg-primary/10 text-primary font-medium'
            : 'text-foreground hover:bg-muted/80'
        )}
      >
        <User className="h-4 w-4 shrink-0 opacity-80" aria-hidden />
        <span className="min-w-0 flex-1 truncate">{entry.employeeName}</span>
        <Badge variant="secondary" className="shrink-0 tabular-nums text-xs">
          {entry.fileCount}
        </Badge>
      </button>
    );
  };

  const desktopFilesPanel = () => {
    const state = renderLoadingOrError();
    if (state) return state;
    if (allEmployeeEntries.length === 0) return renderFolderEmpty(selectedFolder);
    if (filteredEmployeeEntries.length === 0) {
      return (
        <p className="py-12 text-center text-sm text-muted-foreground">
          Aucun collaborateur ne correspond à votre recherche.
        </p>
      );
    }
    return renderEmployeeFiles(selectedGroup, { showFileSearch: false });
  };

  return (
    <div className="space-y-4">
      <Card className="hidden lg:block overflow-hidden">
        <div className="grid min-h-[400px] grid-cols-[minmax(200px,240px)_minmax(200px,260px)_1fr]">
          <div className="border-r bg-muted/30 p-3">
            <p className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Type de document
            </p>
            <nav className="space-y-0.5" aria-label="Types de documents">
              {DOCUMENT_FOLDERS.map((folder) => (
                <div key={folder.id}>{renderFolderButton(folder, 'sidebar')}</div>
              ))}
            </nav>
          </div>

          <div className="flex flex-col border-r bg-muted/15">
            <div className="space-y-2 border-b px-2 py-2.5">
              <div className="px-1">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Collaborateurs
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground truncate">{selectedMeta.label}</p>
              </div>
              {employeeSearchField('desktop')}
            </div>
            <div className="flex-1 overflow-y-auto p-2 max-h-[min(70vh,720px)]">
              {explorerQuery.isLoading && <FileListSkeleton />}
              {!explorerQuery.isLoading && allEmployeeEntries.length === 0 && (
                <p className="px-2 py-6 text-center text-xs text-muted-foreground">Aucun collaborateur.</p>
              )}
              {!explorerQuery.isLoading &&
                allEmployeeEntries.length > 0 &&
                filteredEmployeeEntries.length === 0 && (
                  <p className="px-2 py-6 text-center text-xs text-muted-foreground">
                    Aucun collaborateur ne correspond à votre recherche.
                  </p>
                )}
              <nav className="space-y-0.5" aria-label="Collaborateurs">
                {filteredEmployeeEntries.map(renderEmployeeButton)}
              </nav>
            </div>
          </div>

          <div className="flex flex-col min-w-0">
            <div className="space-y-2 border-b px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-semibold leading-tight truncate">
                    {selectedEmployeeName || selectedMeta.label}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    {selectedGroup
                      ? fileSearch.trim() && selectedFileStats.visible < selectedFileStats.total
                        ? `${selectedFileStats.visible} sur ${selectedFileStats.total} fichier${selectedFileStats.total !== 1 ? 's' : ''}`
                        : `${selectedFileStats.total} fichier${selectedFileStats.total !== 1 ? 's' : ''}`
                      : selectedMeta.label}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {explorerQuery.isFetching && !explorerQuery.isLoading && <LoaderHint />}
                  {headerActions}
                </div>
              </div>
              {selectedGroup && fileSearchField('desktop-files')}
            </div>
            <div className="flex-1 overflow-y-auto p-2 max-h-[min(70vh,720px)]">
              {desktopFilesPanel()}
            </div>
          </div>
        </div>
      </Card>

      <div className="space-y-3 lg:hidden">
        <div className="flex items-center justify-end gap-2">
          {explorerQuery.isFetching && !explorerQuery.isLoading && <LoaderHint />}
          {headerActions}
        </div>
        {DOCUMENT_FOLDERS.map((folder) => {
          const isOpen = mobileOpenFolder === folder.id;
          const empCount = folderData[folder.id].groups.length;
          return (
            <Card key={folder.id} className="overflow-hidden">
              <CardHeader className="py-3">
                <button
                  type="button"
                  className="flex min-w-0 w-full items-center gap-2 text-left"
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
                  <div className="min-w-0 flex-1">
                    <CardTitle className="text-base leading-snug">{folder.label}</CardTitle>
                    <CardDescription className="mt-0.5">
                      {empCount} collaborateur{empCount !== 1 ? 's' : ''} · {folderCounts[folder.id]}{' '}
                      fichier{folderCounts[folder.id] !== 1 ? 's' : ''}
                    </CardDescription>
                  </div>
                </button>
              </CardHeader>
              {isOpen && (
                <CardContent className="pt-0 pb-4">{renderMobileFolderContent(folder.id)}</CardContent>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function mergeEmployeeGroups<
  A extends { meta: EmployeeGroupMeta; items?: ExplorerStorageItem[] },
  B extends { meta: EmployeeGroupMeta; docs?: GeneratedDocument[] },
>(storageGroups: A[], docGroups: B[]) {
  const map = new Map<string, EmployeeGroup>();

  for (const g of storageGroups) {
    const key = g.meta.employeeId;
    const entry = map.get(key) ?? { meta: g.meta, docs: [], items: [] };
    entry.items = [...(entry.items ?? []), ...(g.items ?? [])];
    map.set(key, entry);
  }
  for (const g of docGroups) {
    const key = g.meta.employeeId;
    const entry = map.get(key) ?? { meta: g.meta, docs: [], items: [] };
    entry.docs = [...(entry.docs ?? []), ...(g.docs ?? [])];
    map.set(key, entry);
  }

  return sortEmployeeGroups([...map.values()]);
}

function LoaderHint() {
  return (
    <span className="text-xs text-muted-foreground" aria-live="polite">
      Actualisation…
    </span>
  );
}

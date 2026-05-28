import { useEffect, useState, type ReactNode } from 'react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import {
  DOCUMENT_FOLDERS,
  type DocumentFolderId,
} from '@/components/employee-detail/employeeDetailDocumentsFolders';
import { Folder, FolderOpen, Search } from 'lucide-react';

export interface EmployeeDocumentsFolderExplorerProps {
  folderCounts: Record<DocumentFolderId, number>;
  renderFolderContent: (folderId: DocumentFolderId, fileSearch: string) => ReactNode;
  headerActions?: ReactNode;
  topSlot?: ReactNode;
  /** Libellé de la colonne gauche (défaut : « Dossiers ») */
  foldersNavLabel?: string;
  /** Afficher la recherche dans le panneau fichiers (desktop) */
  showFileSearch?: boolean;
  initialFolder?: DocumentFolderId;
}

export function EmployeeDocumentsFolderExplorer({
  folderCounts,
  renderFolderContent,
  headerActions,
  topSlot,
  foldersNavLabel = 'Dossiers',
  showFileSearch = true,
  initialFolder = 'contrat',
}: EmployeeDocumentsFolderExplorerProps) {
  const [selectedFolder, setSelectedFolder] = useState<DocumentFolderId>(initialFolder);
  const [mobileOpenFolder, setMobileOpenFolder] = useState<DocumentFolderId | null>(initialFolder);
  const [fileSearch, setFileSearch] = useState('');

  useEffect(() => {
    setFileSearch('');
  }, [selectedFolder]);

  const selectedMeta = DOCUMENT_FOLDERS.find((f) => f.id === selectedFolder)!;

  const renderFolderButton = (
    folder: (typeof DOCUMENT_FOLDERS)[number],
    variant: 'sidebar' | 'accordion'
  ) => {
    const count = folderCounts[folder.id];
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
        <span className="min-w-0 flex-1 truncate">{folder.label}</span>
        <Badge variant="secondary" className="shrink-0 tabular-nums">
          {count}
        </Badge>
      </button>
    );
  };

  const fileSearchField = (idSuffix: string) => (
    <div className="relative">
      <Search
        className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
        aria-hidden
      />
      <Input
        id={`employee-doc-file-search-${idSuffix}`}
        type="search"
        placeholder="Rechercher un fichier…"
        value={fileSearch}
        onChange={(e) => setFileSearch(e.target.value)}
        className="h-8 pl-8 text-sm"
        aria-label="Rechercher parmi les fichiers"
      />
    </div>
  );

  return (
    <div className="space-y-4">
      {topSlot}

      <Card className="hidden lg:block overflow-hidden">
        <div className="grid min-h-[320px] grid-cols-[minmax(240px,280px)_1fr]">
          <div className="border-r bg-muted/30 p-3">
            <p className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {foldersNavLabel}
            </p>
            <nav className="space-y-0.5" aria-label="Dossiers documents">
              {DOCUMENT_FOLDERS.map((folder) => (
                <div key={folder.id}>{renderFolderButton(folder, 'sidebar')}</div>
              ))}
            </nav>
          </div>
          <div className="flex flex-col min-w-0">
            <div className="space-y-2 border-b px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-semibold leading-tight">{selectedMeta.label}</h3>
                  <p className="text-xs text-muted-foreground">
                    {folderCounts[selectedFolder]} fichier
                    {folderCounts[selectedFolder] !== 1 ? 's' : ''}
                  </p>
                </div>
                {headerActions ? (
                  <div className="flex shrink-0 items-center gap-2">{headerActions}</div>
                ) : null}
              </div>
              {showFileSearch ? fileSearchField('desktop') : null}
            </div>
            <div className="flex-1 overflow-y-auto p-2 max-h-[min(70vh,720px)]">
              {renderFolderContent(selectedFolder, fileSearch)}
            </div>
          </div>
        </div>
      </Card>

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
                  {headerActions ? (
                    <div className="flex shrink-0 items-center">{headerActions}</div>
                  ) : null}
                </div>
              </CardHeader>
              {isOpen && (
                <CardContent className="space-y-3 pt-0 pb-4">
                  {showFileSearch ? fileSearchField(`mobile-${folder.id}`) : null}
                  {renderFolderContent(folder.id, fileSearch)}
                </CardContent>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}

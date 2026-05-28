import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { BDESDocument, BDESDocumentType, MeetingListItem } from '@/api/cse';
import {
  downloadBDESDocument,
  getMeetingMinutesPathIfAvailable,
} from '@/api/cse';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useToast } from '@/components/ui/use-toast';
import { BDES_TYPE_LABELS } from '@/lib/cseLabels';
import { formatCseDate, formatPublishedAt } from '@/lib/employeeCseUtils';
import { Download, FileText, Loader2 } from 'lucide-react';

type DocumentListItem =
  | { kind: 'bdes'; doc: BDESDocument; sortDate: string }
  | { kind: 'meeting-pv'; meeting: MeetingListItem; sortDate: string };

interface EmployeeCseDocumentsTabProps {
  documents: BDESDocument[];
  meetingsWithMinutes: MeetingListItem[];
  isLoading: boolean;
  isError?: boolean;
}

export function EmployeeCseDocumentsTab({
  documents,
  meetingsWithMinutes,
  isLoading,
  isError,
}: EmployeeCseDocumentsTabProps) {
  const { toast } = useToast();
  const [searchTerm, setSearchTerm] = useState('');
  const [yearFilter, setYearFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const currentYear = new Date().getFullYear();

  const yearOptions = useMemo(() => {
    const years = new Set<number>();
    documents.forEach((d) => {
      if (d.year != null) years.add(d.year);
    });
    meetingsWithMinutes.forEach((m) => {
      years.add(new Date(m.meeting_date).getFullYear());
    });
    years.add(currentYear);
    return Array.from(years).sort((a, b) => b - a);
  }, [documents, meetingsWithMinutes, currentYear]);

  const unifiedItems = useMemo((): DocumentListItem[] => {
    const items: DocumentListItem[] = documents.map((doc) => ({
      kind: 'bdes' as const,
      doc,
      sortDate: doc.published_at ?? doc.created_at,
    }));

    meetingsWithMinutes.forEach((meeting) => {
      const alreadyListed = documents.some(
        (d) =>
          d.document_type === 'pv' &&
          d.year === new Date(meeting.meeting_date).getFullYear() &&
          d.title.toLowerCase().includes(meeting.title.toLowerCase().slice(0, 20))
      );
      if (!alreadyListed) {
        items.push({
          kind: 'meeting-pv',
          meeting,
          sortDate: meeting.meeting_date,
        });
      }
    });

    return items.sort(
      (a, b) => new Date(b.sortDate).getTime() - new Date(a.sortDate).getTime()
    );
  }, [documents, meetingsWithMinutes]);

  const filteredItems = useMemo(() => {
    return unifiedItems.filter((item) => {
      if (item.kind === 'bdes') {
        const doc = item.doc;
        if (typeFilter !== 'all' && doc.document_type !== typeFilter) return false;
        if (yearFilter !== 'all' && doc.year !== Number(yearFilter)) return false;
        if (searchTerm) {
          const s = searchTerm.toLowerCase();
          return (
            doc.title.toLowerCase().includes(s) ||
            (doc.description?.toLowerCase().includes(s) ?? false)
          );
        }
        return true;
      }

      if (typeFilter === 'bdes') return false;
      if (typeFilter !== 'all' && typeFilter !== 'pv') return false;
      const year = new Date(item.meeting.meeting_date).getFullYear();
      if (yearFilter !== 'all' && year !== Number(yearFilter)) return false;
      if (searchTerm) {
        const s = searchTerm.toLowerCase();
        return item.meeting.title.toLowerCase().includes(s);
      }
      return true;
    });
  }, [unifiedItems, searchTerm, yearFilter, typeFilter]);

  const groupedByYear = useMemo(() => {
    const groups = new Map<number, DocumentListItem[]>();
    filteredItems.forEach((item) => {
      const year =
        item.kind === 'bdes'
          ? item.doc.year ?? new Date(item.sortDate).getFullYear()
          : new Date(item.meeting.meeting_date).getFullYear();
      const list = groups.get(year) ?? [];
      list.push(item);
      groups.set(year, list);
    });
    return Array.from(groups.entries()).sort(([a], [b]) => b - a);
  }, [filteredItems]);

  const handleDownloadBdes = async (doc: BDESDocument) => {
    setDownloadingId(doc.id);
    try {
      const url = await downloadBDESDocument(doc.id);
      window.open(url, '_blank');
    } catch {
      toast({
        title: 'Échec du téléchargement',
        description: 'Impossible de télécharger ce document.',
        variant: 'destructive',
      });
    } finally {
      setDownloadingId(null);
    }
  };

  const handleDownloadMeetingPv = async (meeting: MeetingListItem) => {
    setDownloadingId(`meeting-${meeting.id}`);
    try {
      const path = await getMeetingMinutesPathIfAvailable(meeting.id);
      if (path) {
        window.open(path, '_blank');
      } else {
        toast({
          title: 'PV indisponible',
          description: 'Le procès-verbal n’est pas encore disponible au téléchargement.',
          variant: 'destructive',
        });
      }
    } catch {
      toast({
        title: 'Échec du téléchargement',
        description: 'Impossible de récupérer le procès-verbal.',
        variant: 'destructive',
      });
    } finally {
      setDownloadingId(null);
    }
  };

  if (isError) {
    return (
      <Card className="border-destructive/50">
        <CardContent className="pt-6 text-sm text-destructive">
          Impossible de charger les documents. Réessayez plus tard.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        <Input
          placeholder="Rechercher un document…"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="max-w-sm"
        />
        <Select value={yearFilter} onValueChange={setYearFilter}>
          <SelectTrigger className="w-[130px]">
            <SelectValue placeholder="Année" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Toutes années</SelectItem>
            {yearOptions.map((y) => (
              <SelectItem key={y} value={String(y)}>
                {y}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous types</SelectItem>
            {(Object.keys(BDES_TYPE_LABELS) as BDESDocumentType[]).map((t) => (
              <SelectItem key={t} value={t}>
                {BDES_TYPE_LABELS[t]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Documents BDES et procès-verbaux
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : groupedByYear.length === 0 ? (
            <p className="py-8 text-center text-muted-foreground">
              Aucun document trouvé pour ces critères.
            </p>
          ) : (
            <TooltipProvider>
              <div className="space-y-6">
                {groupedByYear.map(([year, items]) => (
                  <div key={year}>
                    <h3 className="mb-3 text-sm font-semibold text-muted-foreground">
                      {year}
                    </h3>
                    <ul className="space-y-2">
                      {items.map((item) =>
                        item.kind === 'bdes' ? (
                          <BdesRow
                            key={item.doc.id}
                            doc={item.doc}
                            downloading={downloadingId === item.doc.id}
                            onDownload={() => handleDownloadBdes(item.doc)}
                          />
                        ) : (
                          <MeetingPvRow
                            key={item.meeting.id}
                            meeting={item.meeting}
                            downloading={downloadingId === `meeting-${item.meeting.id}`}
                            onDownload={() => handleDownloadMeetingPv(item.meeting)}
                          />
                        )
                      )}
                    </ul>
                  </div>
                ))}
              </div>
            </TooltipProvider>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function BdesRow({
  doc,
  downloading,
  onDownload,
}: {
  doc: BDESDocument;
  downloading: boolean;
  onDownload: () => void;
}) {
  return (
    <li className="flex flex-col gap-2 rounded-md border p-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        {doc.description ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <p className="cursor-help font-medium underline decoration-dotted underline-offset-2">
                {doc.title}
              </p>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              <p>{doc.description}</p>
            </TooltipContent>
          </Tooltip>
        ) : (
          <p className="font-medium">{doc.title}</p>
        )}
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="outline">{BDES_TYPE_LABELS[doc.document_type]}</Badge>
          <span>Publié le {formatPublishedAt(doc.published_at)}</span>
          {doc.published_by_name ? <span>par {doc.published_by_name}</span> : null}
        </div>
      </div>
      <Button
        variant="outline"
        size="sm"
        className="shrink-0"
        disabled={downloading}
        onClick={onDownload}
      >
        {downloading ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <Download className="mr-2 h-4 w-4" />
        )}
        Télécharger
      </Button>
    </li>
  );
}

function MeetingPvRow({
  meeting,
  downloading,
  onDownload,
}: {
  meeting: MeetingListItem;
  downloading: boolean;
  onDownload: () => void;
}) {
  return (
    <li className="flex flex-col gap-2 rounded-md border p-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="font-medium">PV — {meeting.title}</p>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="outline">{BDES_TYPE_LABELS.pv}</Badge>
          <span>Réunion du {formatCseDate(meeting.meeting_date)}</span>
        </div>
      </div>
      <div className="flex shrink-0 gap-2">
        <Button variant="ghost" size="sm" asChild>
          <Link to={`/cse/meetings/${meeting.id}`}>Détail</Link>
        </Button>
        <Button variant="outline" size="sm" disabled={downloading} onClick={onDownload}>
          {downloading ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Download className="mr-2 h-4 w-4" />
          )}
          Télécharger
        </Button>
      </div>
    </li>
  );
}

// frontend/src/pages/cse/BDESTab.tsx

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useToast } from "@/components/ui/use-toast";
import {
  getBDESDocuments,
  downloadBDESDocument,
  type BDESDocument,
  type BDESDocumentType,
} from "@/api/cse";
import { BDES_TYPE_LABELS } from "@/lib/cseLabels";
import { Plus, FileText, Download, Loader2 } from "lucide-react";
import { BDESUploadModal } from "@/components/cse/BDESUploadModal";

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export default function BDESTab() {
  const { toast } = useToast();
  const [searchTerm, setSearchTerm] = useState("");
  const [yearFilter, setYearFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [uploadModalOpen, setUploadModalOpen] = useState(false);

  const currentYear = new Date().getFullYear();
  const yearParam = yearFilter !== "all" ? Number(yearFilter) : undefined;
  const typeParam =
    typeFilter !== "all" ? (typeFilter as BDESDocumentType) : undefined;

  const { data: documents = [], isLoading } = useQuery({
    queryKey: ["cse", "bdes-documents", yearParam, typeParam],
    queryFn: () => getBDESDocuments(yearParam, typeParam),
  });

  const yearOptions = useMemo(() => {
    const years = new Set(documents.map((d) => d.year).filter((y): y is number => y != null));
    years.add(currentYear);
    return Array.from(years).sort((a, b) => b - a);
  }, [documents, currentYear]);

  const filteredDocuments = documents.filter((doc) => {
    if (!searchTerm) return true;
    const search = searchTerm.toLowerCase();
    return (
      doc.title.toLowerCase().includes(search) ||
      (doc.description?.toLowerCase().includes(search) ?? false)
    );
  });

  const handleDownload = async (doc: BDESDocument) => {
    try {
      const url = await downloadBDESDocument(doc.id);
      window.open(url, "_blank");
    } catch (error: unknown) {
      const msg =
        error && typeof error === "object" && "message" in error
          ? String((error as { message?: string }).message)
          : "Impossible de télécharger ce document.";
      toast({
        title: "Échec du téléchargement",
        description: msg,
        variant: "destructive",
      });
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <Input
            placeholder="Rechercher un document…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="max-w-sm"
          />
          <Select value={yearFilter} onValueChange={setYearFilter}>
            <SelectTrigger className="w-[120px]">
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
        <Button onClick={() => setUploadModalOpen(true)} className="shrink-0">
          <Plus className="h-4 w-4 mr-2" />
          Ajouter un document
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Documents BDES
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : filteredDocuments.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">Aucun document trouvé</div>
          ) : (
            <TooltipProvider>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Titre</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Année</TableHead>
                    <TableHead>Publié le</TableHead>
                    <TableHead>Par</TableHead>
                    <TableHead>Visibilité</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredDocuments.map((doc) => (
                    <TableRow key={doc.id}>
                      <TableCell className="font-medium max-w-[200px]">
                        {doc.description ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="cursor-help underline decoration-dotted underline-offset-2">
                                {doc.title}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent className="max-w-xs">
                              <p>{doc.description}</p>
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          doc.title
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          {BDES_TYPE_LABELS[doc.document_type] ?? doc.document_type}
                        </Badge>
                      </TableCell>
                      <TableCell>{doc.year ?? "—"}</TableCell>
                      <TableCell>{formatDateTime(doc.published_at)}</TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {doc.published_by_name ?? "—"}
                      </TableCell>
                      <TableCell>
                        <Badge variant={doc.is_visible_to_elected ? "default" : "secondary"}>
                          {doc.is_visible_to_elected ? "Visible élus" : "RH uniquement"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          title="Télécharger"
                          onClick={() => handleDownload(doc)}
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TooltipProvider>
          )}
        </CardContent>
      </Card>

      {uploadModalOpen && (
        <BDESUploadModal open={uploadModalOpen} onOpenChange={setUploadModalOpen} />
      )}
    </div>
  );
}

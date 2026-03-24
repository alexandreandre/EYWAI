// frontend/src/pages/cse/BDESTab.tsx
// Onglet Documents BDES

import { useState } from "react";
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
import { Badge } from "@/components/ui/badge";
import { getBDESDocuments, downloadBDESDocument, type BDESDocument } from "@/api/cse";
import { Plus, FileText, Download, Loader2 } from "lucide-react";
import { BDESUploadModal } from "@/components/cse/BDESUploadModal";

export default function BDESTab() {
  const [searchTerm, setSearchTerm] = useState("");
  const [uploadModalOpen, setUploadModalOpen] = useState(false);

  const { data: documents = [], isLoading } = useQuery({
    queryKey: ["cse", "bdes-documents"],
    queryFn: () => getBDESDocuments(),
  });

  const filteredDocuments = documents.filter((doc) => {
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      return (
        doc.title.toLowerCase().includes(search) ||
        doc.description?.toLowerCase().includes(search) ||
        ""
      );
    }
    return true;
  });

  const handleDownload = async (documentId: string) => {
    try {
      const url = await downloadBDESDocument(documentId);
      window.open(url, "_blank");
    } catch (error) {
      console.error("Erreur lors du téléchargement:", error);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4 flex-1">
          <Input
            placeholder="Rechercher un document..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="max-w-sm"
          />
        </div>
        <Button onClick={() => setUploadModalOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Ajouter un document
        </Button>
      </div>

      {/* Liste des documents */}
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
            <div className="text-center py-8 text-muted-foreground">
              Aucun document trouvé
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Titre</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Année</TableHead>
                  <TableHead>Visibilité</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredDocuments.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell className="font-medium">{doc.title}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{doc.document_type}</Badge>
                    </TableCell>
                    <TableCell>{doc.year || "—"}</TableCell>
                    <TableCell>
                      <Badge variant={doc.is_visible_to_elected ? "default" : "secondary"}>
                        {doc.is_visible_to_elected ? "Visible élus" : "RH uniquement"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDownload(doc.id)}
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Modal upload */}
      {uploadModalOpen && (
        <BDESUploadModal
          open={uploadModalOpen}
          onOpenChange={setUploadModalOpen}
        />
      )}
    </div>
  );
}

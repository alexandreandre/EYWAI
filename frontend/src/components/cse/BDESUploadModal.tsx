// frontend/src/components/cse/BDESUploadModal.tsx
// Modal pour uploader un document BDES

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/components/ui/use-toast";
import { uploadBDESDocument, type BDESDocumentType } from "@/api/cse";
import { Loader2, Upload } from "lucide-react";
import apiClient from "@/api/apiClient";

interface BDESUploadModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function BDESUploadModal({ open, onOpenChange }: BDESUploadModalProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [documentType, setDocumentType] = useState<BDESDocumentType>("bdes");
  const [year, setYear] = useState(new Date().getFullYear().toString());
  const [description, setDescription] = useState("");
  const [isVisibleToElected, setIsVisibleToElected] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      // D'abord uploader le fichier vers Supabase Storage
      // Note: Cette partie nécessite un endpoint backend pour générer l'URL signée
      // Pour l'instant, on simule l'upload
      const formData = new FormData();
      formData.append("file", file);
      
      // Générer une URL d'upload signée (à implémenter avec le backend)
      const uploadResponse = await apiClient.post("/api/uploads/bdes", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      
      const filePath = uploadResponse.data.path;
      
      // Ensuite créer le document BDES
      return uploadBDESDocument(file, {
        title,
        document_type: documentType,
        file_path: filePath,
        year: parseInt(year) || null,
        is_visible_to_elected: isVisibleToElected,
        description: description || null,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cse", "bdes-documents"] });
      toast({
        title: "Document uploadé",
        description: "Le document BDES a été ajouté avec succès.",
      });
      onOpenChange(false);
      // Reset form
      setTitle("");
      setDocumentType("bdes");
      setYear(new Date().getFullYear().toString());
      setDescription("");
      setIsVisibleToElected(true);
      setFile(null);
    },
    onError: (error: any) => {
      toast({
        title: "Erreur",
        description: error.message || "Erreur lors de l'upload",
        variant: "destructive",
      });
    },
  });

  const handleSubmit = async () => {
    if (!title || !file) {
      toast({
        title: "Champs requis",
        description: "Le titre et le fichier sont obligatoires",
        variant: "destructive",
      });
      return;
    }

    uploadMutation.mutate(file);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Ajouter un document BDES</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="title">Titre *</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Ex: BDES 2026"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="type">Type de document *</Label>
              <Select value={documentType} onValueChange={(v: any) => setDocumentType(v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="bdes">BDES</SelectItem>
                  <SelectItem value="pv">PV</SelectItem>
                  <SelectItem value="autre">Autre</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="year">Année</Label>
              <Input
                id="year"
                type="number"
                value={year}
                onChange={(e) => setYear(e.target.value)}
                placeholder={new Date().getFullYear().toString()}
              />
            </div>
          </div>
          <div>
            <Label htmlFor="file">Fichier *</Label>
            <div className="flex items-center gap-2">
              <Input
                id="file"
                type="file"
                accept=".pdf,.doc,.docx"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="flex-1"
              />
              {file && (
                <span className="text-sm text-muted-foreground">
                  {file.name}
                </span>
              )}
            </div>
          </div>
          <div>
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description du document"
              rows={3}
            />
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              id="visible"
              checked={isVisibleToElected}
              onCheckedChange={(checked) => setIsVisibleToElected(checked === true)}
            />
            <Label htmlFor="visible" className="cursor-pointer">
              Visible pour les élus
            </Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button onClick={handleSubmit} disabled={uploadMutation.isPending}>
            {uploadMutation.isPending && (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            )}
            <Upload className="h-4 w-4 mr-2" />
            Uploader
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Fichier : src/pages/Expenses.tsx (Côté RH - VERSION FINALE)

import { useState, useEffect, useCallback } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { Loader2, Check, X, Clock, Download, Eye } from "lucide-react";
import apiClient from '@/api/apiClient'; // <-- AJOUTER
import type * as expensesApi from '@/api/expenses'; // <-- CHANGER en 'import type'

type ExpenseRequest = expensesApi.ExpenseWithEmployee;

export default function ExpensesPage() {
  const { toast } = useToast();
  const [pending, setPending] = useState<ExpenseRequest[]>([]);
  const [processed, setProcessed] = useState<ExpenseRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      // On utilise apiClient avec les URL relatives (en HTTPS)
      const [pendingRes, validatedRes, rejectedRes] = await Promise.all([
        apiClient.get<ExpenseRequest[]>(`/api/expenses/?status=pending`),
        apiClient.get<ExpenseRequest[]>(`/api/expenses/?status=validated`),
        apiClient.get<ExpenseRequest[]>(`/api/expenses/?status=rejected`),
      ]);
      setPending(pendingRes.data);
      // On fusionne et trie les demandes traitées (validées et refusées) par date de création
      const allProcessed = [...validatedRes.data, ...rejectedRes.data];
      setProcessed(allProcessed.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()));
    } catch (error) {
      toast({ title: "Erreur", description: "Impossible de charger les notes de frais.", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  }, [toast]); // Ajout de 'toast' dans les dépendances

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleUpdateStatus = async (id: string, status: 'validated' | 'rejected') => {
    try {
      // On utilise apiClient.patch pour mettre à jour la ressource
      await apiClient.patch(`/api/expenses/${id}`, { status: status });
      toast({ title: "Succès", description: "La note de frais a été mise à jour." });
      fetchData();
    } catch (error) {
      toast({ title: "Erreur", description: "La mise à jour a échoué.", variant: "destructive" });
    }
  };

  const getReceiptUrl = (path: string | null) => {
    if (!path) return null;
    const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
    if (!SUPABASE_URL) {
      console.error("Erreur: VITE_SUPABASE_URL n'est pas définie dans le fichier .env du frontend !");
      return "#";
    }
    return `${SUPABASE_URL}/storage/v1/object/public/expense_receipts/${path}`;
  };

  // --- NOUVELLE FONCTION POUR GÉRER LE TÉLÉCHARGEMENT ---
  const handleDownload = async (expense: expensesApi.Expense) => {
  const path = expense.receipt_url;
  if (!path) return;

  const url = getReceiptUrl(path);
  if (!url || url === "#") return;

  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Erreur HTTP: ${response.statusText}`);

    // 1. Lecture du blob + type MIME
    const blob = await response.blob();
    const mimeType = blob.type || "application/octet-stream";

    // 2. Déduction d'une extension à partir du MIME type
    const mimeExtensions: Record<string, string> = {
      "application/pdf": ".pdf",
      "image/jpeg": ".jpg",
      "image/png": ".png",
      "image/heic": ".heic",
      "image/webp": ".webp",
      "image/tiff": ".tiff",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
      "application/msword": ".doc",
      "application/vnd.ms-excel": ".xls",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
      "text/plain": ".txt",
      "text/csv": ".csv",
      "application/zip": ".zip",
    };
    const defaultExtension = mimeExtensions[mimeType] || "";

    // 3. Nom de fichier : utilise celui stocké, sinon extrait, sinon fallback
    let filename =
      expense.filename ||
      path.split("/").pop() ||
      "justificatif" + defaultExtension;

    // 4. Ajoute l’extension si absente
    if (!/\.[a-zA-Z0-9]+$/.test(filename)) filename += defaultExtension || ".bin";

    // 5. Déclenche le téléchargement
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(objectUrl);
  } catch (error) {
    console.error("Erreur de téléchargement:", error);
    toast({
      title: "Erreur",
      description: "Impossible de télécharger le fichier.",
      variant: "destructive",
    });
  }
};

  // --- FIN DE LA NOUVELLE FONCTION ---

  const renderRequestsTable = (requests: ExpenseRequest[]) => (
    <Table>
      <TableHeader><TableRow>
        <TableHead>Employé</TableHead><TableHead>Date</TableHead><TableHead>Type</TableHead>
        <TableHead>Montant</TableHead><TableHead>Justificatif</TableHead><TableHead className="text-right">Actions</TableHead>
      </TableRow></TableHeader>
      <TableBody>
        {requests.map(req => (
          <TableRow key={req.id}>
            <TableCell className="font-medium">{req.employee.first_name} {req.employee.last_name}</TableCell>
            <TableCell>{new Date(req.date).toLocaleDateString('fr-FR')}</TableCell>
            <TableCell>{req.type}</TableCell>
            <TableCell>{req.amount.toFixed(2)} €</TableCell>
            <TableCell>
              {req.receipt_url && (
                <div className="flex gap-2">
                  {/* Bouton Voir (inchangé) */}
                  <Button variant="outline" size="icon" asChild>
                    <a href={getReceiptUrl(req.receipt_url)} target="_blank" rel="noopener noreferrer" title="Voir le justificatif">
                      <Eye className="h-4 w-4" />
                    </a>
                  </Button>
                  {/* Bouton Télécharger MODIFIÉ */}
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => handleDownload(req)} // <-- Passe l'objet 'req' entier
                    title="Télécharger le justificatif"
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </TableCell>
            <TableCell className="text-right">
              {req.status === 'pending' ? (
                <div className="flex gap-2 justify-end">
                  <Button size="sm" variant="destructive" onClick={() => handleUpdateStatus(req.id, 'rejected')}><X className="mr-2 h-4 w-4" /> Rejeter</Button>
                  <Button size="sm" onClick={() => handleUpdateStatus(req.id, 'validated')}><Check className="mr-2 h-4 w-4" /> Approuver</Button>
                </div>
              ) : (
                <Badge variant={req.status === 'validated' ? 'success' : 'destructive'}>
                  {req.status === 'validated' ? 'Approuvée' : 'Rejetée'}
                </Badge>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Gestion des Notes de Frais</h1>
      <Tabs defaultValue="pending">
        <TabsList>
          <TabsTrigger value="pending"><Clock className="mr-2 h-4 w-4" /> En attente <Badge className="ml-2">{pending.length}</Badge></TabsTrigger>
          <TabsTrigger value="processed">Historique</TabsTrigger>
        </TabsList>
        <TabsContent value="pending"><Card><CardHeader><CardTitle>Demandes à valider</CardTitle></CardHeader><CardContent>{isLoading ? <Loader2 className="mx-auto h-8 w-8 animate-spin" /> : renderRequestsTable(pending)}</CardContent></Card></TabsContent>
        <TabsContent value="processed"><Card><CardHeader><CardTitle>Demandes traitées</CardTitle></CardHeader><CardContent>{isLoading ? <Loader2 className="mx-auto h-8 w-8 animate-spin" /> : renderRequestsTable(processed)}</CardContent></Card></TabsContent>
      </Tabs>
    </div>
  );
}
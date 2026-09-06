// Fichier : src/pages/Expenses.tsx (Côté RH - VERSION FINALE)

import { log } from '@/lib/logger';
import { RhPageHeader } from '@/components/layout';
import { useState, useEffect, useCallback } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { Check, X, Clock, Download, Eye, Pencil, Plus, Trash2 } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { NewExpenseModal } from "@/components/NewExpenseModal";
import { SharkFinLoader } from '@/components/SharkFinLoader';
import axios from 'axios';
import { downloadBlob } from '@/lib/downloadBlob';
import * as expensesApi from '@/api/expenses';
import { formatExpenseVatSummary } from '@/lib/expenseVat';

type ExpenseRequest = expensesApi.ExpenseWithEmployee;

export default function ExpensesPage() {
  const { toast } = useToast();
  const [showNewExpense, setShowNewExpense] = useState(false);
  const [editingExpense, setEditingExpense] = useState<ExpenseRequest | null>(null);
  const [deletingExpense, setDeletingExpense] = useState<ExpenseRequest | null>(null);
  const [pending, setPending] = useState<ExpenseRequest[]>([]);
  const [processed, setProcessed] = useState<ExpenseRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  /** RH : une saisie directe est validée tout de suite → onglet Historique. */
  const [activeTab, setActiveTab] = useState("pending");

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [pendingRes, validatedRes, rejectedRes] = await Promise.all([
        expensesApi.getAllExpenses('pending'),
        expensesApi.getAllExpenses('validated'),
        expensesApi.getAllExpenses('rejected'),
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

  const handleDelete = async () => {
    if (!deletingExpense) return;
    const etaitValidee = deletingExpense.status === 'validated';
    try {
      await expensesApi.deleteExpense(deletingExpense.id);
      toast({
        title: "Succès",
        description: etaitValidee
          ? "Note supprimée. Si le bulletin du mois est déjà généré, régénérez-le pour retirer le remboursement."
          : "Note de frais supprimée.",
      });
      setDeletingExpense(null);
      fetchData();
    } catch (err) {
      log.error('Suppression de note de frais échouée:', err);
      const detail =
        axios.isAxiosError(err) && typeof err.response?.data?.detail === 'string'
          ? err.response.data.detail
          : "La suppression a échoué.";
      toast({ title: "Erreur", description: detail, variant: "destructive" });
    }
  };

  const handleUpdateStatus = async (id: string, status: 'validated' | 'rejected') => {
    try {
      await expensesApi.updateExpenseStatus(id, status);
      toast({ title: "Succès", description: "La note de frais a été mise à jour." });
      fetchData();
    } catch (error) {
      toast({ title: "Erreur", description: "La mise à jour a échoué.", variant: "destructive" });
    }
  };

  // Le bucket des justificatifs est PRIVÉ depuis l'audit du 23/08/2026 : on
  // demande une URL signée au backend au lieu de fabriquer une URL publique.
  const ouvrirJustificatif = async (path: string | null) => {
    if (!path) return;
    try {
      const url = await expensesApi.getReceiptSignedUrl(path);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (error) {
      log.error("Justificatif : URL signée indisponible", error);
      toast({
        title: "Erreur",
        description: "Le justificatif n'a pas pu être ouvert.",
        variant: "destructive",
      });
    }
  };

  // --- NOUVELLE FONCTION POUR GÉRER LE TÉLÉCHARGEMENT ---
  const handleDownload = async (expense: expensesApi.Expense) => {
  const path = expense.receipt_url;
  if (!path) return;

  let url: string;
  try {
    url = await expensesApi.getReceiptSignedUrl(path);
  } catch (error) {
    log.error("Justificatif : URL signée indisponible", error);
    toast({
      title: "Erreur",
      description: "Le justificatif n'a pas pu être téléchargé.",
      variant: "destructive",
    });
    return;
  }

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
    downloadBlob(blob, filename);
  } catch (error) {
    log.error("Erreur de téléchargement:", error);
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
        <TableHead>Montant TTC</TableHead><TableHead>TVA</TableHead><TableHead>Justificatif</TableHead><TableHead className="text-right">Actions</TableHead>
      </TableRow></TableHeader>
      <TableBody>
        {requests.map(req => (
          <TableRow key={req.id}>
            <TableCell className="font-medium">{req.employee.first_name} {req.employee.last_name}</TableCell>
            <TableCell>{new Date(req.date).toLocaleDateString('fr-FR')}</TableCell>
            <TableCell>{req.type}</TableCell>
            <TableCell className="tabular-nums whitespace-nowrap">{req.amount.toFixed(2)} €</TableCell>
            <TableCell className="text-xs text-muted-foreground tabular-nums max-w-[12rem]">
              {formatExpenseVatSummary(req, { includeTtc: false }) ?? '—'}
            </TableCell>
            <TableCell>
              {req.receipt_url && (
                <div className="flex gap-2">
                  {/* Bouton Voir (inchangé) */}
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => ouvrirJustificatif(req.receipt_url)}
                    title="Voir le justificatif"
                  >
                    <Eye className="h-4 w-4" />
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
              <div className="flex items-center gap-2 justify-end">
                {req.status === 'pending' ? (
                  <>
                    <Button size="sm" variant="destructive" onClick={() => handleUpdateStatus(req.id, 'rejected')}><X className="mr-2 h-4 w-4" /> Rejeter</Button>
                    <Button size="sm" onClick={() => handleUpdateStatus(req.id, 'validated')}><Check className="mr-2 h-4 w-4" /> Approuver</Button>
                  </>
                ) : (
                  <Badge variant={req.status === 'validated' ? 'success' : 'destructive'}>
                    {req.status === 'validated' ? 'Approuvée' : 'Rejetée'}
                  </Badge>
                )}
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setEditingExpense(req)}
                  title="Modifier la note"
                >
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setDeletingExpense(req)}
                  title="Supprimer la note"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );

  return (
    <div className="space-y-6">
      <RhPageHeader
        title="Gestion des Notes de Frais"
        actions={
          <Button onClick={() => setShowNewExpense(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Nouvelle note de frais
          </Button>
        }
      />
      <NewExpenseModal
        isOpen={showNewExpense}
        onClose={() => setShowNewExpense(false)}
        onSuccess={() => {
          setActiveTab("processed");
          void fetchData();
        }}
        showEmployeeSelector
      />
      <NewExpenseModal
        isOpen={editingExpense != null}
        onClose={() => setEditingExpense(null)}
        onSuccess={() => {
          if (editingExpense?.status === 'validated') {
            toast({
              title: 'Pensez au bulletin',
              description:
                'Cette note était validée : si le bulletin du mois est déjà généré, régénérez-le pour reprendre le bon montant.',
            });
          }
          void fetchData();
        }}
        expense={editingExpense}
      />
      <AlertDialog
        open={deletingExpense != null}
        onOpenChange={(open) => !open && setDeletingExpense(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer cette note de frais ?</AlertDialogTitle>
            <AlertDialogDescription>
              {deletingExpense
                ? `${deletingExpense.employee.first_name} ${deletingExpense.employee.last_name} — ${deletingExpense.type}, ${deletingExpense.amount.toFixed(2)} € TTC. La suppression est définitive.`
                : ""}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete}>Supprimer</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="pending"><Clock className="mr-2 h-4 w-4" /> En attente <Badge className="ml-2">{pending.length}</Badge></TabsTrigger>
          <TabsTrigger value="processed">Historique <Badge className="ml-2">{processed.length}</Badge></TabsTrigger>
        </TabsList>
        <TabsContent value="pending"><Card><CardHeader><CardTitle>Demandes à valider</CardTitle></CardHeader><CardContent>{isLoading ? <SharkFinLoader label="Chargement des demandes…" /> : renderRequestsTable(pending)}</CardContent></Card></TabsContent>
        <TabsContent value="processed"><Card><CardHeader><CardTitle>Demandes traitées</CardTitle></CardHeader><CardContent>{isLoading ? <SharkFinLoader label="Chargement des demandes…" /> : renderRequestsTable(processed)}</CardContent></Card></TabsContent>
      </Tabs>
    </div>
  );
}
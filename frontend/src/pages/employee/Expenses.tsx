// Fichier : src/pages/employee/Expenses.tsx (VERSION COMPLÈTE ET FINALE CORRIGÉE)

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { PlusCircle, Camera, CheckCircle, Clock, CircleX, Download, Eye } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { NewExpenseModal } from '@/components/NewExpenseModal';
import { Loader2 } from 'lucide-react';
import apiClient from '@/api/apiClient'; // <-- AJOUTER
import type * as expensesApi from '@/api/expenses'; // <-- CHANGER en 'import type'


export default function ExpensesPage() {
  const { toast } = useToast();
  const [expenses, setExpenses] = useState<expensesApi.Expense[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);


  // eslint-disable-next-line react-hooks/exhaustive-deps
  const fetchExpenses = useCallback(async () => {
    setIsLoading(true);
    try {
      // On utilise apiClient avec l'URL relative (en HTTPS)
      const response = await apiClient.get<expensesApi.Expense[]>('/api/expenses/me');
      setExpenses(response.data);
    } catch (err) {
      toast({ title: "Erreur", description: "Impossible de charger les notes de frais.", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  }, []);


  useEffect(() => { fetchExpenses(); }, [fetchExpenses]);

  const getStatusBadge = (status: expensesApi.ExpenseStatus) => {
    switch (status) {
      case 'validated': return <Badge variant="success"><CheckCircle className="mr-1 h-3 w-3"/>Approuvée</Badge>;
      case 'pending': return <Badge variant="secondary"><Clock className="mr-1 h-3 w-3"/>En attente</Badge>;
      case 'rejected': return <Badge variant="destructive"><CircleX className="mr-1 h-3 w-3"/>Rejetée</Badge>;
      default: return <Badge>{status}</Badge>;
    }
  };

  const handleDownload = async (expense: expensesApi.Expense) => {
    // Le backend nous fournit déjà une URL signée complète et valide.
    const signedUrl = expense.receipt_url;
    if (!signedUrl) {
      toast({ title: "Erreur", description: "Aucun justificatif associé à cette dépense.", variant: "destructive" });
      return;
    }

    try {
      // On fetch le contenu du fichier depuis l'URL signée.
      const response = await fetch(signedUrl);
      if (!response.ok) {
        throw new Error(`Erreur réseau: ${response.statusText}`);
      }
      const blob = await response.blob();

      // On crée une URL locale pour le blob et on simule un clic pour le téléchargement.
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = expense.filename || "justificatif";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url); // Libère la mémoire
    } catch (error) {
      console.error("Erreur lors de la tentative de téléchargement:", error);
      toast({ title: "Erreur", description: "Impossible de lancer le téléchargement.", variant: "destructive" });
    }
  };

  return (
    <>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">Mes Notes de Frais</h1>
          <Button onClick={() => setIsModalOpen(true)}><PlusCircle className="mr-2 h-4 w-4" /> Nouvelle dépense</Button>
        </div>

        <Card>
          <CardHeader><CardTitle>Suivi des dépenses</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader><TableRow>
                <TableHead>Date</TableHead><TableHead>Type</TableHead><TableHead>Montant</TableHead>
                <TableHead>Justificatif</TableHead><TableHead className="text-right">Statut</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {isLoading ? (
                    <TableRow><TableCell colSpan={5} className="h-24 text-center"><Loader2 className="h-6 w-6 animate-spin mx-auto" /></TableCell></TableRow>
                ) : expenses.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell className="font-medium">{new Date(e.date).toLocaleDateString('fr-FR')}</TableCell>
                    <TableCell>{e.type}</TableCell>
                    <TableCell>{e.amount.toFixed(2)} €</TableCell>
                    <TableCell>
                      {e.receipt_url && (
                        <div className="flex gap-2">
                          {/* Bouton Voir */}
                          <Button variant="outline" size="icon" asChild>
                            <a href={e.receipt_url || '#'} target="_blank" rel="noopener noreferrer" title="Voir le justificatif">
                              <Eye className="h-4 w-4" />
                            </a>
                          </Button>
                          {/* Bouton Télécharger */}
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => handleDownload(e)}
                            title="Télécharger le justificatif"
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-right">{getStatusBadge(e.status)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
      <NewExpenseModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} onSuccess={fetchExpenses} />
    </>
  );
}
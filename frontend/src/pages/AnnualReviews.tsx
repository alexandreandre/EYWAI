// src/pages/AnnualReviews.tsx
// Page RH : liste et suivi des entretiens

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { useCompany } from "@/contexts/CompanyContext";
import { AnnualReviewBadge } from "@/components/AnnualReviewBadge";
import apiClient from "@/api/apiClient";
import {
  getAllAnnualReviews,
  createAnnualReview,
  deleteAnnualReview,
  downloadAnnualReviewPdf,
} from "@/api/annualReviews";
import type {
  AnnualReviewListItem,
  AnnualReviewStatus,
} from "@/api/annualReviews";
import { Loader2, Search, MessageSquare, Plus, ChevronRight, Trash2, FileDown, Eye } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

const STATUS_FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "Tous" },
  { value: "a_planifier", label: "À planifier" },
  { value: "planifie", label: "Planifié" },
  { value: "en_preparation", label: "En préparation" },
  { value: "prete", label: "Prêt" },
  { value: "realise", label: "Réalisé" },
  { value: "cloture", label: "Clôturé" },
];

function formatDate(value: string | null): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return value;
  }
}

export default function AnnualReviews() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? "";

  const [filterYear, setFilterYear] = useState<number | "all">("all");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [planningModalOpen, setPlanningModalOpen] = useState(false);
  const [planningEmployeeId, setPlanningEmployeeId] = useState("");
  const [planningDate, setPlanningDate] = useState("");
  const [planningTemplate, setPlanningTemplate] = useState("");

  const currentYear = new Date().getFullYear();
  const yearOptions = Array.from({ length: 6 }, (_, i) => currentYear - i);

  const {
    data: list = [],
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["annual-reviews", filterYear === "all" ? null : filterYear, filterStatus === "all" ? null : filterStatus, activeCompanyId],
    queryFn: async () => {
      const res = await getAllAnnualReviews({
        year: filterYear === "all" ? undefined : filterYear,
        status: filterStatus === "all" ? undefined : filterStatus,
      });
      return res.data;
    },
    enabled: !!activeCompanyId,
  });

  const { data: employees = [] } = useQuery({
    queryKey: ["employees", activeCompanyId],
    queryFn: async () => {
      const res = await apiClient.get("/api/employees");
      return res.data;
    },
    enabled: !!activeCompanyId && planningModalOpen,
  });

  const createMutation = useMutation({
    mutationFn: createAnnualReview,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["annual-reviews"] });
      setPlanningModalOpen(false);
      setPlanningEmployeeId("");
      setPlanningDate("");
      setPlanningTemplate("");
      toast({ 
        title: "Entretien créé", 
        description: "L'entretien a été créé en statut \"En attente d'acceptation\". L'employé peut maintenant l'accepter ou la refuser."
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Impossible de planifier l'entretien.",
        variant: "destructive",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteAnnualReview,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["annual-reviews"] });
      toast({ title: "Entretien supprimé", description: "L'entretien a été supprimé avec succès." });
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Impossible de supprimer l'entretien.",
        variant: "destructive",
      });
    },
  });

  useEffect(() => {
    if (isError) {
      toast({
        title: "Erreur",
        description:
          (error as Error)?.message ?? "Impossible de charger les entretiens.",
        variant: "destructive",
      });
    }
  }, [isError, error, toast]);

  const filteredList = useMemo(() => {
    let items: AnnualReviewListItem[] = list;
    if (searchTerm.trim()) {
      const term = searchTerm.trim().toLowerCase();
      items = items.filter(
        (item) =>
          item.first_name.toLowerCase().includes(term) ||
          item.last_name.toLowerCase().includes(term)
      );
    }
    return items;
  }, [list, searchTerm]);

  const isEmpty = list.length === 0;
  const noResults = !isEmpty && filteredList.length === 0;

  const handleOpenPlanning = () => {
    setPlanningEmployeeId("");
    setPlanningDate("");
    setPlanningTemplate("");
    setPlanningModalOpen(true);
  };

  const handlePlanSubmit = () => {
    if (!planningEmployeeId) {
      toast({
        title: "Champ requis",
        description: "Veuillez sélectionner un employé.",
        variant: "destructive",
      });
      return;
    }
    // Calculer l'année automatiquement : depuis la date prévue ou année courante
    const year = planningDate 
      ? new Date(planningDate).getFullYear()
      : new Date().getFullYear();
    
    createMutation.mutate({
      employee_id: planningEmployeeId,
      year: year,
      planned_date: planningDate ? planningDate : null,
      rh_preparation_template: planningTemplate || null,
    });
  };

  const handleViewPdf = async (reviewId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const blob = await downloadAnnualReviewPdf(reviewId);
      const url = window.URL.createObjectURL(blob);
      window.open(url, '_blank');
      // Ne pas révoquer immédiatement l'URL pour permettre l'ouverture dans un nouvel onglet
      setTimeout(() => window.URL.revokeObjectURL(url), 100);
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error?.response?.data?.detail || "Impossible d'ouvrir le PDF.",
        variant: "destructive",
      });
    }
  };

  const handleDownloadPdf = async (reviewId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const blob = await downloadAnnualReviewPdf(reviewId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `entretien_${reviewId}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast({
        title: "PDF téléchargé",
        description: "Le PDF de l'entretien a été téléchargé avec succès.",
      });
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error?.response?.data?.detail || "Impossible de télécharger le PDF.",
        variant: "destructive",
      });
    }
  };

  // Plus de filtre : on peut créer plusieurs entretiens pour le même employé

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Entretiens</h1>
        <p className="text-muted-foreground mt-2">
          Suivi des entretiens des collaborateurs
          {activeCompany?.company_name ? ` — ${activeCompany.company_name}` : ""}.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-col sm:flex-row gap-4 items-stretch sm:items-center justify-between">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Rechercher par nom ou prénom..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="flex flex-wrap gap-2 items-center">
              <div className="flex items-center gap-2">
                <Select
                  value={filterYear === "all" ? "all" : String(filterYear)}
                  onValueChange={(v) =>
                    setFilterYear(v === "all" ? "all" : Number(v))
                  }
                >
                  <SelectTrigger className="w-[140px]">
                    <SelectValue placeholder="Date" />
                  </SelectTrigger>
                  <SelectContent>
                  <SelectItem value="all"><span className="block w-full text-left">Toutes les dates</span></SelectItem>

                    {yearOptions.map((y) => (
                      <SelectItem key={y} value={String(y)}>
                        {y}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Select
                value={filterStatus}
                onValueChange={setFilterStatus}
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Statut" />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_FILTER_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button onClick={handleOpenPlanning}>
                <Plus className="mr-2 h-4 w-4" />
                Planifier un entretien
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center h-48">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : isError ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-destructive">
              <p className="font-medium">Erreur de chargement</p>
              <p className="text-sm mt-1 text-muted-foreground">
                {(error as Error)?.message ?? "Impossible de charger les entretiens."}
              </p>
            </div>
          ) : isEmpty ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
              <MessageSquare className="h-12 w-12 mb-4 opacity-50" />
              <p className="font-medium">Aucun entretien</p>
              <p className="text-sm mt-1">
                Planifiez un entretien pour commencer le suivi.
              </p>
              
            </div>
          ) : noResults ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
              <Search className="h-12 w-12 mb-4 opacity-50" />
              <p className="font-medium">Aucun résultat</p>
              <p className="text-sm mt-1">
                Modifiez le filtre ou la recherche.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Collaborateur</TableHead>
                  <TableHead>Poste</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead className="w-[100px]">PDF</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredList.map((item) => (
                  <TableRow 
                    key={item.id}
                    className="cursor-pointer hover:bg-muted/50 transition-colors"
                    onClick={() => navigate(`/annual-reviews/${item.id}`)}
                  >
                    <TableCell className="font-medium">
                      {item.first_name} {item.last_name}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {item.job_title ?? "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {item.completed_date 
                        ? formatDate(item.completed_date)
                        : item.planned_date 
                        ? formatDate(item.planned_date)
                        : item.year}
                    </TableCell>
                    <TableCell>
                      <AnnualReviewBadge
                        status={item.status as AnnualReviewStatus}
                        compact
                      />
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      {item.status === "cloture" ? (
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => handleViewPdf(item.id, e)}
                            className="h-8 w-8 p-0"
                            title="Voir le PDF"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => handleDownloadPdf(item.id, e)}
                            className="h-8 w-8 p-0"
                            title="Télécharger le PDF"
                          >
                            <FileDown className="h-4 w-4" />
                          </Button>
                        </div>
                      ) : (
                        <span className="text-muted-foreground text-xs">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Supprimer l'entretien</AlertDialogTitle>
                            <AlertDialogDescription>
                              Êtes-vous sûr de vouloir supprimer l'entretien de {item.first_name} {item.last_name} ?
                              Cette action est irréversible.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Annuler</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => deleteMutation.mutate(item.id)}
                              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                              disabled={deleteMutation.isPending}
                            >
                              {deleteMutation.isPending ? (
                                <>
                                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                  Suppression...
                                </>
                              ) : (
                                "Supprimer"
                              )}
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={planningModalOpen} onOpenChange={setPlanningModalOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Planifier un entretien</DialogTitle>
          </DialogHeader>
          <div className="grid gap-6 py-4">
            <div className="grid gap-2">
              <Label htmlFor="employee-select">Employé *</Label>
              <Select
                value={planningEmployeeId}
                onValueChange={setPlanningEmployeeId}
              >
                <SelectTrigger id="employee-select">
                  <SelectValue placeholder="Sélectionner un employé" />
                </SelectTrigger>
                <SelectContent>
                  {employees.map((emp) => (
                    <SelectItem key={emp.id} value={emp.id}>
                      {emp.first_name} {emp.last_name}
                    </SelectItem>
                  ))}
                  {employees.length === 0 && (
                    <SelectItem value="_" disabled>
                      Aucun employé disponible
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="planned-date">Date prévue</Label>
              <Input
                id="planned-date"
                type="date"
                value={planningDate}
                onChange={(e) => setPlanningDate(e.target.value)}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="preparation-template">
                Notes (visible par l'employé)
              </Label>
              <Textarea
                id="preparation-template"
                placeholder="Rédigez ici vos notes pour l'entretien. Ces notes seront visibles par l'employé qui pourra l'accepter ou la refuser.

Exemples de points à inclure :
• Objectifs de l'entretien
• Points à aborder
• Documents à préparer
• Questions à réfléchir en amont..."
                value={planningTemplate}
                onChange={(e) => setPlanningTemplate(e.target.value)}
                rows={8}
                className="resize-none min-h-[200px]"
              />
              <p className="text-xs text-muted-foreground">
                L'entretien sera créé en statut "En attente d'acceptation" et l'employé pourra l'accepter ou la refuser.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPlanningModalOpen(false)}>
              Annuler
            </Button>
            <Button
              onClick={handlePlanSubmit}
              disabled={!planningEmployeeId || createMutation.isPending}
            >
              {createMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Planifier l'entretien
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

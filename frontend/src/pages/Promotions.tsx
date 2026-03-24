// frontend/src/pages/Promotions.tsx
// Page RH : liste et gestion des promotions

import { useMemo, useState } from "react";
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
import { PromotionBadge } from "@/components/PromotionBadge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  getPromotions,
  getPromotion,
  deletePromotion,
  markPromotionEffective,
  getPromotionStats,
} from "@/api/promotions";
import { PromotionModal } from "@/components/PromotionModal";
import type { Promotion } from "@/api/promotions";
import type {
  PromotionListItem,
  PromotionStatus,
  PromotionType,
} from "@/api/promotions";
import {
  Loader2,
  Search,
  Plus,
  Eye,
  Edit,
  CheckCircle2,
  Trash2,
  TrendingUp,
  Calendar,
  Users,
} from "lucide-react";
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
import { Badge } from "@/components/ui/badge";

const STATUS_FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "Tous" },
  { value: "draft", label: "Brouillon" },
  { value: "effective", label: "Effective" },
  { value: "cancelled", label: "Annulée" },
];

const TYPE_FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "Tous" },
  { value: "poste", label: "Changement de poste" },
  { value: "salaire", label: "Augmentation de salaire" },
  { value: "statut", label: "Changement de statut" },
  { value: "classification", label: "Changement de classification" },
  { value: "mixte", label: "Promotion mixte" },
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

function formatCurrency(salary: { valeur: number; devise: string } | null): string {
  if (!salary || !salary.valeur) return "—";
  return `${salary.valeur.toLocaleString("fr-FR")} ${salary.devise || "EUR"}`;
}

function getEvolutionText(promotion: PromotionListItem): string {
  const parts: string[] = [];
  if (promotion.new_job_title) {
    parts.push(promotion.new_job_title);
  }
  if (promotion.new_salary) {
    parts.push(formatCurrency(promotion.new_salary));
  }
  if (promotion.new_statut) {
    parts.push(promotion.new_statut);
  }
  return parts.length > 0 ? parts.join(" • ") : "—";
}

export default function Promotions() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? "";

  const [filterYear, setFilterYear] = useState<number | "all">("all");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [filterType, setFilterType] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [activeTab, setActiveTab] = useState<"all" | "draft" | "effective">("all");

  // États pour les modals
  const [promotionModalOpen, setPromotionModalOpen] = useState(false);
  const [promotionToEdit, setPromotionToEdit] = useState<Promotion | null>(null);

  const currentYear = new Date().getFullYear();
  const yearOptions = Array.from({ length: 6 }, (_, i) => currentYear - i);

  // Charger les promotions
  const {
    data: list = [],
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: [
      "promotions",
      filterYear === "all" ? null : filterYear,
      filterStatus === "all" ? null : filterStatus,
      filterType === "all" ? null : filterType,
      searchTerm || null,
      activeCompanyId,
    ],
    queryFn: async () => {
      const res = await getPromotions({
        year: filterYear === "all" ? undefined : filterYear,
        status: filterStatus === "all" ? undefined : (filterStatus as PromotionStatus),
        promotion_type: filterType === "all" ? undefined : (filterType as PromotionType),
        search: searchTerm || undefined,
      });
      return res.data;
    },
    enabled: !!activeCompanyId,
  });

  // Charger les statistiques
  const { data: stats } = useQuery({
    queryKey: ["promotion-stats", filterYear === "all" ? null : filterYear, activeCompanyId],
    queryFn: async () => {
      const res = await getPromotionStats(
        filterYear === "all" ? undefined : filterYear
      );
      return res.data;
    },
    enabled: !!activeCompanyId,
  });

  // Mutations
  const markEffectiveMutation = useMutation({
    mutationFn: markPromotionEffective,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["promotions"] });
      queryClient.invalidateQueries({ queryKey: ["promotion-stats"] });
      toast({
        title: "Promotion effective",
        description: "La promotion a été marquée comme effective et les changements ont été appliqués.",
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Impossible de marquer la promotion comme effective.",
        variant: "destructive",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deletePromotion,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["promotions"] });
      queryClient.invalidateQueries({ queryKey: ["promotion-stats"] });
      toast({
        title: "Promotion supprimée",
        description: "La promotion a été supprimée avec succès.",
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Impossible de supprimer la promotion.",
        variant: "destructive",
      });
    },
  });


  // Filtrer selon l'onglet actif
  const filteredList = useMemo(() => {
    let items: PromotionListItem[] = list;

    // Filtre par onglet
    if (activeTab === "draft") {
      items = items.filter((item) => item.status === "draft");
    } else if (activeTab === "effective") {
      items = items.filter((item) => item.status === "effective");
    }

    // Filtre par recherche
    if (searchTerm.trim()) {
      const term = searchTerm.trim().toLowerCase();
      items = items.filter(
        (item) =>
          item.first_name.toLowerCase().includes(term) ||
          item.last_name.toLowerCase().includes(term) ||
          (item.new_job_title?.toLowerCase().includes(term) ?? false)
      );
    }

    return items;
  }, [list, activeTab, searchTerm]);

  const isEmpty = list.length === 0;
  const noResults = !isEmpty && filteredList.length === 0;


  const handleResetFilters = () => {
    setFilterYear("all");
    setFilterStatus("all");
    setFilterType("all");
    setSearchTerm("");
    setActiveTab("all");
  };

  // Calculer les statistiques rapides
  const draftCount = list.filter((p) => p.status === "draft").length;
  const thisMonthCount = list.filter((p) => {
    const date = new Date(p.effective_date);
    return (
      date.getMonth() === new Date().getMonth() &&
      date.getFullYear() === new Date().getFullYear()
    );
  }).length;
  const thisYearCount = list.filter((p) => {
    const date = new Date(p.effective_date);
    return date.getFullYear() === new Date().getFullYear();
  }).length;

  return (
    <div className="space-y-6">
      {/* Header avec statistiques */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold">Promotions</h1>
            <p className="text-muted-foreground mt-2">
              Gestion des promotions et évolutions de carrière
              {activeCompany?.company_name ? ` — ${activeCompany.company_name}` : ""}
            </p>
          </div>
          <Button onClick={() => { setPromotionToEdit(null); setPromotionModalOpen(true); }}>
            <Plus className="mr-2 h-4 w-4" />
            Nouvelle promotion
          </Button>
        </div>

        {/* Statistiques rapides */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Brouillons</p>
                  <p className="text-2xl font-bold">{draftCount}</p>
                </div>
                <div className="h-12 w-12 rounded-full bg-amber-100 flex items-center justify-center">
                  <Calendar className="h-6 w-6 text-amber-600" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Ce mois</p>
                  <p className="text-2xl font-bold">{thisMonthCount}</p>
                </div>
                <div className="h-12 w-12 rounded-full bg-blue-100 flex items-center justify-center">
                  <TrendingUp className="h-6 w-6 text-blue-600" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Cette année</p>
                  <p className="text-2xl font-bold">{thisYearCount}</p>
                </div>
                <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
                  <Users className="h-6 w-6 text-green-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-col gap-4">
            {/* Barre de filtres */}
            <div className="flex flex-col sm:flex-row gap-4 items-stretch sm:items-center justify-between">
              <div className="relative flex-1 max-w-sm">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Rechercher par nom, prénom ou poste..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
              <div className="flex flex-wrap gap-2 items-center">
                <Select
                  value={filterYear === "all" ? "all" : String(filterYear)}
                  onValueChange={(v) =>
                    setFilterYear(v === "all" ? "all" : Number(v))
                  }
                >
                  <SelectTrigger className="w-[140px]">
                    <SelectValue placeholder="Année" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Toutes les années</SelectItem>
                    {yearOptions.map((y) => (
                      <SelectItem key={y} value={String(y)}>
                        {y}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select value={filterStatus} onValueChange={setFilterStatus}>
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
                <Select value={filterType} onValueChange={setFilterType}>
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Type" />
                  </SelectTrigger>
                  <SelectContent>
                    {TYPE_FILTER_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button variant="outline" onClick={handleResetFilters}>
                  Réinitialiser
                </Button>
              </div>
            </div>

            {/* Onglets */}
            <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)} className="w-full">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="all">Toutes</TabsTrigger>
                <TabsTrigger value="draft" className="flex items-center gap-2">
                  Brouillons
                  {draftCount > 0 && (
                    <Badge variant="secondary" className="ml-1">
                      {draftCount}
                    </Badge>
                  )}
                </TabsTrigger>
                <TabsTrigger value="effective">Effectives</TabsTrigger>
              </TabsList>
            </Tabs>
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
                {(error as Error)?.message ?? "Impossible de charger les promotions."}
              </p>
            </div>
          ) : isEmpty ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
              <TrendingUp className="h-12 w-12 mb-4 opacity-50" />
              <p className="font-medium">Aucune promotion</p>
              <p className="text-sm mt-1">
                Créez une nouvelle promotion pour commencer.
              </p>
              <Button
                className="mt-4"
                onClick={() => { setPromotionToEdit(null); setPromotionModalOpen(true); }}
              >
                <Plus className="mr-2 h-4 w-4" />
                Créer une promotion
              </Button>
            </div>
          ) : noResults ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
              <Search className="h-12 w-12 mb-4 opacity-50" />
              <p className="font-medium">Aucun résultat</p>
              <p className="text-sm mt-1">
                Modifiez les filtres ou la recherche.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Employé</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Évolution</TableHead>
                  <TableHead>Date d'effet</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredList.map((item) => (
                  <TableRow
                    key={item.id}
                    className="cursor-pointer hover:bg-muted/50 transition-colors"
                    onClick={() => navigate(`/promotions/${item.id}`)}
                  >
                    <TableCell className="font-medium">
                      {item.first_name} {item.last_name}
                    </TableCell>
                    <TableCell>
                      <PromotionBadge
                        type={item.promotion_type}
                        variant="type"
                        compact
                      />
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {getEvolutionText(item)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(item.effective_date)}
                    </TableCell>
                    <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate(`/promotions/${item.id}`)}
                          className="h-8 w-8 p-0"
                          title="Voir les détails"
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        {item.status === "draft" && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={async () => {
                                try {
                                  const res = await getPromotion(item.id);
                                  setPromotionToEdit(res.data);
                                  setPromotionModalOpen(true);
                                } catch {
                                  toast({
                                    title: "Erreur",
                                    description: "Impossible de charger la promotion.",
                                    variant: "destructive",
                                  });
                                }
                              }}
                              className="h-8 w-8 p-0"
                              title="Modifier"
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => markEffectiveMutation.mutate(item.id)}
                              className="h-8 w-8 p-0 text-green-600"
                              title="Marquer comme effective"
                              disabled={markEffectiveMutation.isPending}
                            >
                              <CheckCircle2 className="h-4 w-4" />
                            </Button>
                          </>
                        )}
                        {item.status === "draft" && (
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                                title="Supprimer"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Supprimer la promotion</AlertDialogTitle>
                                <AlertDialogDescription>
                                  Êtes-vous sûr de vouloir supprimer la promotion de {item.first_name} {item.last_name} ?
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
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Modal de création / édition */}
      <PromotionModal
        isOpen={promotionModalOpen}
        onClose={() => { setPromotionModalOpen(false); setPromotionToEdit(null); }}
        promotion={promotionToEdit}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ["promotions"] });
          queryClient.invalidateQueries({ queryKey: ["promotion-stats"] });
          setPromotionModalOpen(false);
          setPromotionToEdit(null);
        }}
      />

    </div>
  );
}

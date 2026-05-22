import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { FileSignature, FileText, Loader2, TrendingUp } from "lucide-react";

import type { Promotion } from "@/api/promotions";
import { CareerActivityTable } from "@/components/career/CareerActivityTable";
import { CareerFiltersBar } from "@/components/career/CareerFiltersBar";
import { CareerQuickActions } from "@/components/career/CareerQuickActions";
import { SalaryReviewDrawer } from "@/components/career/SalaryReviewDrawer";
import type { CareerActivityTab } from "@/components/career/types";
import { PromotionModal } from "@/components/PromotionModal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useCompany } from "@/contexts/CompanyContext";
import { useCareerActivity } from "@/hooks/useCareerActivity";
import { computeCareerKpis } from "@/lib/careerActivity";

const TAB_LABELS: Record<CareerActivityTab, string> = {
  all: "Tout",
  promotion: "Promotions",
  salary_review_session: "Augmentations",
  avenant: "Avenants",
};

const TAB_HINTS: Record<CareerActivityTab, string> = {
  all: "Vue d'ensemble : promotions et campagnes d'augmentation collective (sans liste détaillée des avenants).",
  promotion: "Dossiers de promotion et évolutions de carrière par collaborateur.",
  salary_review_session:
    "Campagnes d'augmentation collective : lots appliqués regroupés par date et motif.",
  avenant: "Avenants salaire générés — téléchargement et suivi de signature.",
};

export default function AugmentationsEtPromotions() {
  const queryClient = useQueryClient();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? "";

  const [searchTerm, setSearchTerm] = useState("");
  const [filterYear, setFilterYear] = useState<number | "all">("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterType, setFilterType] = useState("all");
  const [activeTab, setActiveTab] = useState<CareerActivityTab>("all");

  const [promotionModalOpen, setPromotionModalOpen] = useState(false);
  const [promotionToEdit, setPromotionToEdit] = useState<Promotion | null>(null);
  const [salaryReviewOpen, setSalaryReviewOpen] = useState(false);

  const { items, tabCounts, promotions, avenants, isLoading, isError, error, refetch } =
    useCareerActivity(companyId, {
      search: searchTerm,
      year: filterYear,
      status: filterStatus,
      type: filterType,
      tab: activeTab,
    });

  const careerKpis = useMemo(
    () => computeCareerKpis(promotions, avenants),
    [promotions, avenants],
  );

  const handleResetFilters = () => {
    setSearchTerm("");
    setFilterYear("all");
    setFilterStatus("all");
    setFilterType("all");
    setActiveTab("all");
  };

  const refreshActivity = () => {
    void queryClient.invalidateQueries({ queryKey: ["promotions"] });
    void queryClient.invalidateQueries({ queryKey: ["documents", "avenant_salaire"] });
    refetch();
  };

  const openNewPromotion = () => {
    setPromotionToEdit(null);
    setPromotionModalOpen(true);
  };

  const isEmpty = !isLoading && items.length === 0;

  const resultLabel = useMemo(() => {
    const n = items.length;
    if (n === 0) return "Aucun élément";
    if (n === 1) return "1 élément";
    return `${n} éléments`;
  }, [items.length]);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Augmentations & Promotions</h1>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          Pilotez les augmentations de salaire (collectives ou par avenant) et les promotions de
          carrière depuis un seul registre.
          {activeCompany?.company_name ? ` — ${activeCompany.company_name}` : ""}
        </p>
      </div>

      <CareerQuickActions
        onAugmentationCollective={() => setSalaryReviewOpen(true)}
        onNewPromotion={openNewPromotion}
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <TrendingUp className="text-muted-foreground h-8 w-8 shrink-0" aria-hidden />
            <div>
              <p className="text-muted-foreground text-xs font-medium uppercase">
                Promotions {new Date().getFullYear()}
              </p>
              <p className="text-2xl font-bold tabular-nums">{careerKpis.promotionsThisYear}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <FileText className="text-muted-foreground h-8 w-8 shrink-0" aria-hidden />
            <div>
              <p className="text-muted-foreground text-xs font-medium uppercase">
                Brouillons
              </p>
              <p className="text-2xl font-bold tabular-nums">{careerKpis.draftPromotions}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <TrendingUp className="text-muted-foreground h-8 w-8 shrink-0" aria-hidden />
            <div>
              <p className="text-muted-foreground text-xs font-medium uppercase">
                Campagnes 12 mois
              </p>
              <p className="text-2xl font-bold tabular-nums">
                {careerKpis.reviewSessions12Months}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <FileSignature className="text-muted-foreground h-8 w-8 shrink-0" aria-hidden />
            <div>
              <p className="text-muted-foreground text-xs font-medium uppercase">
                Avenants à signer
              </p>
              <p className="text-2xl font-bold tabular-nums">{careerKpis.avenantsToSign}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="space-y-4 border-b pb-4">
          <div>
            <CardTitle className="text-lg">Registre d&apos;activité</CardTitle>
            <CardDescription className="mt-1">{TAB_HINTS[activeTab]}</CardDescription>
          </div>

          <Tabs
            value={activeTab}
            onValueChange={(v) => setActiveTab(v as CareerActivityTab)}
            className="w-full"
          >
            <TabsList className="grid h-auto w-full grid-cols-2 gap-1 p-1 lg:grid-cols-4">
              {(Object.keys(TAB_LABELS) as CareerActivityTab[]).map((tab) => (
                <TabsTrigger
                  key={tab}
                  value={tab}
                  className="flex items-center justify-center gap-2 py-2.5 data-[state=active]:shadow-sm"
                >
                  <span>{TAB_LABELS[tab]}</span>
                  <Badge
                    variant={activeTab === tab ? "default" : "secondary"}
                    className="h-5 min-w-[1.25rem] px-1.5 text-xs tabular-nums"
                  >
                    {tabCounts[tab]}
                  </Badge>
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          <CareerFiltersBar
            search={searchTerm}
            onSearchChange={setSearchTerm}
            year={filterYear}
            onYearChange={setFilterYear}
            status={filterStatus}
            onStatusChange={setFilterStatus}
            type={filterType}
            onTypeChange={setFilterType}
            activeTab={activeTab}
            onReset={handleResetFilters}
          />
        </CardHeader>

        <CardContent className="pt-6">
          {!isLoading && !isError && !isEmpty && (
            <p className="mb-4 text-sm text-muted-foreground">
              {resultLabel}
              {searchTerm.trim() ? ` pour « ${searchTerm.trim()} »` : ""}
            </p>
          )}

          {isLoading ? (
            <div className="flex h-48 justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : isError ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-destructive">
              <p className="font-medium">Erreur de chargement</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {(error as Error)?.message ?? "Impossible de charger le registre."}
              </p>
              <Button variant="outline" className="mt-4" onClick={() => refetch()}>
                Réessayer
              </Button>
            </div>
          ) : isEmpty ? (
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center text-muted-foreground">
              <TrendingUp className="mb-4 h-12 w-12 opacity-40" />
              <p className="font-medium text-foreground">Aucun élément dans cet onglet</p>
              <p className="mt-1 max-w-md text-sm">
                {activeTab === "salary_review_session"
                  ? "Lancez une augmentation collective pour créer des campagnes et des avenants."
                  : activeTab === "promotion"
                    ? "Créez une promotion pour suivre une évolution de carrière."
                    : activeTab === "avenant"
                      ? "Les avenants apparaissent après génération depuis l'outil d'augmentation collective."
                      : "Ajustez les filtres ou créez une première activité via les actions ci-dessus."}
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {(activeTab === "all" || activeTab === "salary_review_session") && (
                  <Button onClick={() => setSalaryReviewOpen(true)}>Augmentation collective</Button>
                )}
                {(activeTab === "all" || activeTab === "promotion") && (
                  <Button variant="outline" onClick={openNewPromotion}>
                    Nouvelle promotion
                  </Button>
                )}
                {(filterYear !== "all" ||
                  filterStatus !== "all" ||
                  filterType !== "all" ||
                  searchTerm.trim()) && (
                  <Button variant="ghost" onClick={handleResetFilters}>
                    Réinitialiser les filtres
                  </Button>
                )}
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-md border">
              <CareerActivityTable
                items={items}
                companyId={companyId}
                onEditPromotion={(p) => {
                  setPromotionToEdit(p);
                  setPromotionModalOpen(true);
                }}
              />
            </div>
          )}
        </CardContent>
      </Card>

      <PromotionModal
        isOpen={promotionModalOpen}
        onClose={() => {
          setPromotionModalOpen(false);
          setPromotionToEdit(null);
        }}
        promotion={promotionToEdit}
        onSuccess={() => {
          refreshActivity();
          setPromotionModalOpen(false);
          setPromotionToEdit(null);
        }}
      />

      <SalaryReviewDrawer
        open={salaryReviewOpen}
        onOpenChange={setSalaryReviewOpen}
        companyId={companyId}
        onActivityRefresh={refreshActivity}
      />
    </div>
  );
}

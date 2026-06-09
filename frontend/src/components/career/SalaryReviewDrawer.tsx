import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { TrendingUp } from "lucide-react";

import {
  appliquerAugmentationCollective,
  genererAvenantsLot,
  simulerAugmentationCollective,
  type SimulationCollectiveResultat,
} from "@/api/augmentations";
import { getDocuments } from "@/api/documents";
import { listCompanyServices } from "@/api/objectives";
import { SalaryReviewApplyDialogs } from "@/components/career/SalaryReviewApplyDialogs";
import {
  SalaryReviewFiltersForm,
  type SalaryReviewFilterState,
} from "@/components/career/SalaryReviewFiltersForm";
import { SalaryReviewSimulationResults } from "@/components/career/SalaryReviewSimulationResults";
import {
  computeAppliedEmployeeIds,
  parseOptionalFloat,
  parseOptionalInt,
} from "@/components/career/salaryReviewUtils";
import { CareerStatusBadge } from "@/components/career/careerStatusBadge";
import { AvenantRowActions } from "@/components/career/AvenantRowActions";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ToastAction } from "@/components/ui/toast";
import { toast } from "@/components/ui/use-toast";
import { AVENANTS_QUERY_KEY } from "@/lib/careerActivity";
import { formatDateFR, formatDateTimeFR } from "@/lib/careerFormat";

const defaultFilters = (): SalaryReviewFilterState => ({
  filterServiceId: "",
  filterStatut: "",
  filterContract: "",
  ancienneteMinMois: "",
  salaireMin: "",
  salaireMax: "",
  simType: "pourcentage",
  perimetre: "brut_et_hs",
  valeurSim: "",
  effectiveDate: new Date().toISOString().slice(0, 10),
});

function docDateEffetDisplay(d: { generation_context: Record<string, unknown> }): string {
  const ctx = d.generation_context;
  if (!ctx || typeof ctx !== "object") return "—";
  const raw = ctx.date_effet;
  if (typeof raw !== "string" || !raw.trim()) return "—";
  return formatDateFR(raw);
}

type SalaryReviewDrawerProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  companyId: string;
  onActivityRefresh?: () => void;
};

export function SalaryReviewDrawer({
  open,
  onOpenChange,
  companyId,
  onActivityRefresh,
}: SalaryReviewDrawerProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [filters, setFilters] = useState<SalaryReviewFilterState>(defaultFilters);
  const [simLoading, setSimLoading] = useState(false);
  const [simResult, setSimResult] = useState<SimulationCollectiveResultat | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const [applyOpen, setApplyOpen] = useState(false);
  const [applyMotif, setApplyMotif] = useState("");
  const [applySubmitting, setApplySubmitting] = useState(false);
  const [applySuccessContext, setApplySuccessContext] = useState<{
    nb_appliques: number;
    appliedIds: string[];
  } | null>(null);
  const applySuccessRef = useRef(applySuccessContext);
  applySuccessRef.current = applySuccessContext;

  const [lotGenOpen, setLotGenOpen] = useState(false);
  const [lotEmployeeIds, setLotEmployeeIds] = useState<string[]>([]);
  const [lotEffectiveDateInput, setLotEffectiveDateInput] = useState("");
  const [lotMotifInput, setLotMotifInput] = useState("");
  const [lotSubmitting, setLotSubmitting] = useState(false);

  const servicesQuery = useQuery({
    queryKey: ["objectives-services"],
    queryFn: () => listCompanyServices(),
    enabled: Boolean(companyId) && open,
  });

  const avenantsQuery = useQuery({
    queryKey: [...AVENANTS_QUERY_KEY, companyId],
    queryFn: () => getDocuments({ document_type: "avenant_salaire" }),
    enabled: Boolean(companyId) && open,
  });

  const employesSimules = simResult?.employes ?? [];

  useEffect(() => {
    if (!simResult?.employes?.length) {
      setSelectedIds(new Set());
      return;
    }
    setSelectedIds(new Set(simResult.employes.map((e) => e.employee_id)));
  }, [simResult]);

  const allSelected = useMemo(() => {
    if (!employesSimules.length) return false;
    return employesSimules.every((e) => selectedIds.has(e.employee_id));
  }, [employesSimules, selectedIds]);

  const patchFilters = (patch: Partial<SalaryReviewFilterState>) => {
    setFilters((prev) => ({ ...prev, ...patch }));
  };

  const resetSimulationUi = () => {
    setSimResult(null);
    setFilters((prev) => ({ ...prev, valeurSim: "" }));
    setApplyMotif("");
    setApplySuccessContext(null);
  };

  const invalidateAll = async () => {
    await queryClient.invalidateQueries({ queryKey: [...AVENANTS_QUERY_KEY, companyId] });
    await queryClient.invalidateQueries({ queryKey: ["promotions"] });
    onActivityRefresh?.();
  };

  const handleSimulate = async () => {
    if (!companyId) {
      toast({ title: "Entreprise active requise", variant: "destructive" });
      return;
    }
    const v = parseFloat(filters.valeurSim.replace(",", "."));
    if (Number.isNaN(v) || v <= 0) {
      toast({ title: "Indiquez une valeur positive.", variant: "destructive" });
      return;
    }

    setSimLoading(true);
    try {
      const data = await simulerAugmentationCollective(companyId, {
        filtres: {
          service_id: filters.filterServiceId || null,
          statut: filters.filterStatut || null,
          contract_type: filters.filterContract || null,
          anciennete_min_mois: parseOptionalInt(filters.ancienneteMinMois),
          salaire_min: parseOptionalFloat(filters.salaireMin),
          salaire_max: parseOptionalFloat(filters.salaireMax),
        },
        type_augmentation: filters.simType,
        valeur: v,
        effective_date: filters.effectiveDate,
        perimetre_augmentation: filters.perimetre,
      });
      setSimResult(data);
      toast({
        title: "Simulation prête",
        description: `${data.nb_employes} salarié(s) correspondant aux filtres.`,
      });
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Simulation impossible",
        description: typeof msg === "string" ? msg : "Réessayez plus tard.",
        variant: "destructive",
      });
    } finally {
      setSimLoading(false);
    }
  };

  const handleApply = async () => {
    if (!companyId || !simResult) return;
    const requested = [...selectedIds];
    if (!requested.length) return;
    const v = parseFloat(filters.valeurSim.replace(",", "."));
    if (Number.isNaN(v) || v <= 0) return;

    setApplySubmitting(true);
    try {
      const res = await appliquerAugmentationCollective(companyId, {
        employee_ids: requested,
        type_augmentation: filters.simType,
        valeur: v,
        effective_date: filters.effectiveDate,
        perimetre_augmentation: filters.perimetre,
        motif: applyMotif.trim() || undefined,
      });

      toast({
        title: "Augmentations appliquées",
        description: `${res.nb_appliques} augmentation(s) enregistrée(s).`,
      });
      if (res.nb_erreurs > 0) {
        toast({
          title: "Certaines lignes ont échoué",
          description: res.erreurs.slice(0, 5).join(" · ") + (res.erreurs.length > 5 ? "…" : ""),
          variant: "destructive",
        });
      }

      const appliedIds = computeAppliedEmployeeIds(requested, res.erreurs);
      if (res.nb_appliques <= 0) {
        setApplyOpen(false);
        resetSimulationUi();
      } else {
        setApplySuccessContext({ nb_appliques: res.nb_appliques, appliedIds });
      }
      await invalidateAll();
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Application impossible",
        description: typeof msg === "string" ? msg : "Réessayez plus tard.",
        variant: "destructive",
      });
    } finally {
      setApplySubmitting(false);
    }
  };

  const closeApplyFlow = () => {
    setApplyOpen(false);
    resetSimulationUi();
  };

  const openLotDialogFromApplySuccess = () => {
    if (!applySuccessContext?.appliedIds.length) return;
    setLotEmployeeIds(applySuccessContext.appliedIds);
    setLotEffectiveDateInput(filters.effectiveDate);
    setLotMotifInput(applyMotif.trim());
    setApplyOpen(false);
    setApplySuccessContext(null);
    setLotGenOpen(true);
  };

  const handleLotGenerate = async () => {
    if (!companyId || !lotEmployeeIds.length) return;
    setLotSubmitting(true);
    try {
      const nouveauParEmploye: Record<string, number> = {};
      if (simResult?.employes?.length) {
        const wanted = new Set(lotEmployeeIds);
        for (const e of simResult.employes) {
          if (wanted.has(e.employee_id)) {
            nouveauParEmploye[e.employee_id] = e.nouveau_salaire_brut;
          }
        }
      }

      const res = await genererAvenantsLot(companyId, {
        employee_ids: lotEmployeeIds,
        effective_date: lotEffectiveDateInput,
        motif: lotMotifInput.trim() || undefined,
        ...(Object.keys(nouveauParEmploye).length > 0
          ? { nouveau_salaire_par_employe: nouveauParEmploye }
          : {}),
      });

      toast({
        title: `${res.nb_generes} avenant(s) généré(s).`,
        description: "Disponibles dans Documents RH pour signature.",
        action: (
          <ToastAction altText="Ouvrir Documents RH" onClick={() => navigate("/documents")}>
            Ouvrir Documents RH
          </ToastAction>
        ),
      });

      if (res.nb_erreurs > 0) {
        toast({
          title: `${res.nb_erreurs} génération(s) en erreur`,
          description: res.erreurs.slice(0, 5).join(" · ") + (res.erreurs.length > 5 ? "…" : ""),
        });
      }

      await invalidateAll();
      setLotGenOpen(false);
      setLotEmployeeIds([]);
      resetSimulationUi();
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Génération impossible",
        description: typeof msg === "string" ? msg : "Réessayez plus tard.",
        variant: "destructive",
      });
    } finally {
      setLotSubmitting(false);
    }
  };

  const rowsAvenants = avenantsQuery.data ?? [];

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent
          side="right"
          className="flex w-full flex-col overflow-y-auto sm:max-w-[min(100vw,1100px)] p-0"
        >
          <SheetHeader className="border-b px-6 py-4 text-left">
            <SheetTitle className="flex items-center gap-2 text-xl">
              <TrendingUp className="h-6 w-6 text-muted-foreground" />
              Augmentation collective
            </SheetTitle>
            <SheetDescription>
              Filtrez les salariés, simulez l&apos;impact sur la masse salariale, appliquez puis
              générez les avenants.
            </SheetDescription>
          </SheetHeader>

          <div className="flex-1 space-y-8 px-6 py-6">
            <div className="grid gap-6 lg:grid-cols-[minmax(260px,320px)_1fr]">
              <SalaryReviewFiltersForm
                filters={filters}
                onChange={patchFilters}
                services={servicesQuery.data ?? []}
                servicesLoading={servicesQuery.isLoading}
                simLoading={simLoading}
                companyId={companyId}
                onSimulate={() => void handleSimulate()}
              />

              <div className="space-y-6">
                {simResult ? (
                  <SalaryReviewSimulationResults
                    simResult={simResult}
                    employes={employesSimules}
                    selectedIds={selectedIds}
                    allSelected={allSelected}
                    onToggleOne={(id, checked) => {
                      setSelectedIds((prev) => {
                        const next = new Set(prev);
                        if (checked) next.add(id);
                        else next.delete(id);
                        return next;
                      });
                    }}
                    onToggleAll={(checked) => {
                      if (!checked || !employesSimules.length) {
                        setSelectedIds(new Set());
                        return;
                      }
                      setSelectedIds(new Set(employesSimules.map((e) => e.employee_id)));
                    }}
                    onApply={() => setApplyOpen(true)}
                  />
                ) : (
                  <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-sm text-muted-foreground">
                      Renseignez les filtres et lancez une simulation pour voir l&apos;impact sur
                      la masse salariale.
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>

            <Separator />

            <section className="space-y-4">
              <div>
                <h3 className="text-lg font-semibold tracking-tight">Avenants émis récemment</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  Suivi des avenants salaire générés pour l&apos;entreprise active.
                </p>
              </div>
              <Card>
                <CardContent className="pt-6">
                  {avenantsQuery.isLoading && (
                    <div className="space-y-3">
                      {[1, 2, 3].map((i) => (
                        <Skeleton key={i} className="h-10 w-full" />
                      ))}
                    </div>
                  )}
                  {!avenantsQuery.isLoading && rowsAvenants.length === 0 && (
                    <p className="py-8 text-center text-sm text-muted-foreground">
                      Aucun avenant salaire généré.
                    </p>
                  )}
                  {!avenantsQuery.isLoading && rowsAvenants.length > 0 && (
                    <div className="w-full overflow-x-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Salarié</TableHead>
                            <TableHead>Génération</TableHead>
                            <TableHead>Date d&apos;effet</TableHead>
                            <TableHead>Statut</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {rowsAvenants.slice(0, 15).map((d) => (
                            <TableRow key={d.id}>
                              <TableCell className="font-medium">
                                {d.employee_name ?? "—"}
                              </TableCell>
                              <TableCell className="whitespace-nowrap text-sm">
                                {formatDateTimeFR(d.created_at)}
                              </TableCell>
                              <TableCell className="whitespace-nowrap text-sm">
                                {docDateEffetDisplay(d)}
                              </TableCell>
                              <TableCell>
                                <CareerStatusBadge kind="avenant" status={d.status} />
                              </TableCell>
                              <TableCell className="text-right">
                                <AvenantRowActions document={d} companyId={companyId} />
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </section>
          </div>
        </SheetContent>
      </Sheet>

      <SalaryReviewApplyDialogs
        applyOpen={applyOpen}
        onApplyOpenChange={(o) => {
          if (!o) {
            const hadSuccess = applySuccessRef.current !== null;
            setApplyOpen(false);
            if (hadSuccess) resetSimulationUi();
          } else {
            setApplyOpen(true);
          }
        }}
        applySuccessContext={applySuccessContext}
        selectedCount={selectedIds.size}
        applyMotif={applyMotif}
        onApplyMotifChange={setApplyMotif}
        effectiveDate={filters.effectiveDate}
        applySubmitting={applySubmitting}
        onConfirmApply={() => void handleApply()}
        onCloseApplyFlow={closeApplyFlow}
        onOpenLotFromSuccess={openLotDialogFromApplySuccess}
        lotGenOpen={lotGenOpen}
        onLotGenOpenChange={setLotGenOpen}
        lotEmployeeCount={lotEmployeeIds.length}
        lotEffectiveDateInput={lotEffectiveDateInput}
        onLotEffectiveDateChange={setLotEffectiveDateInput}
        lotMotifInput={lotMotifInput}
        onLotMotifChange={setLotMotifInput}
        lotSubmitting={lotSubmitting}
        onLotGenerate={() => void handleLotGenerate()}
      />
    </>
  );
}

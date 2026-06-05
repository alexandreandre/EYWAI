import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/api/apiClient";
import {
  appliquerAugmentation,
  getSalaryHistory,
  simulerAugmentation,
  type SimulationResultat,
} from "@/api/augmentations";
import { generateDocument } from "@/api/documents";
import { getEmployeePromotions } from "@/api/promotions";
import type { PromotionListItem } from "@/api/promotions";
import { PromotionModal } from "@/components/PromotionModal";
import { PromotionBadge } from "@/components/PromotionBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/components/ui/use-toast";
import { TAB_AUGMENTATIONS_PROMOTIONS } from "@/features/employee-detail/utils/tabs";
import { formatDateFR, formatEuroAmount, valeurSalaireBrut } from "@/features/employee-detail/utils/formatters";
import type { Employee } from "@/features/employee-detail/types";
import { log } from "@/lib/logger";
import { Award, Calculator, Eye, Loader2, Plus, TrendingUp } from "lucide-react";

interface Props {
  employeeId: string;
  employee: Employee;
  activeCompanyId: string;
  onEmployeeUpdated: (employee: Employee) => void;
}

export function EmployeeDetailAugmentationsPromotionsTab({
  employeeId,
  employee,
  activeCompanyId,
  onEmployeeUpdated,
}: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [augSimType, setAugSimType] = useState<"pourcentage" | "montant_fixe">("pourcentage");
  const [augValeur, setAugValeur] = useState("");
  const [augEffectiveDate, setAugEffectiveDate] = useState(() =>
    new Date().toISOString().slice(0, 10),
  );
  const [augSimLoading, setAugSimLoading] = useState(false);
  const [augSimResult, setAugSimResult] = useState<SimulationResultat | null>(null);
  const [augApplyDialogOpen, setAugApplyDialogOpen] = useState(false);
  const [augApplyMotif, setAugApplyMotif] = useState("");
  const [augApplySubmitting, setAugApplySubmitting] = useState(false);
  const [augGenDraft, setAugGenDraft] = useState<{
    nouveau_brut: number;
    effective_date: string;
    motif: string;
  } | null>(null);
  const [augGenDialogOpen, setAugGenDialogOpen] = useState(false);
  const [augGenDateInput, setAugGenDateInput] = useState("");
  const [augGenMotifInput, setAugGenMotifInput] = useState("");

  const salaryHistoryQuery = useQuery({
    queryKey: ["salary-history", employeeId, activeCompanyId],
    queryFn: () => getSalaryHistory(employeeId, activeCompanyId),
    enabled: Boolean(employeeId && activeCompanyId),
  });

  const augSalariatGenMut = useMutation({
    mutationFn: generateDocument,
    onSuccess: async () => {
      queryClient.invalidateQueries({ queryKey: ["employee-generated-documents", employeeId] });
      setAugGenDialogOpen(false);
      setAugGenDraft(null);
      toast({
        title: "Avenant salaire généré",
        description: "Le PDF est disponible dans l’onglet Documents.",
      });
    },
    onError: (e: unknown) => {
      const msg =
        e && typeof e === "object" && "response" in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Échec",
        description: typeof msg === "string" ? msg : "Génération impossible.",
        variant: "destructive",
      });
    },
  });

  const [promotions, setPromotions] = useState<PromotionListItem[]>([]);
  const [promotionsLoading, setPromotionsLoading] = useState(false);
  const [promotionModalOpen, setPromotionModalOpen] = useState(false);

  const fetchPromotions = useCallback(async () => {
    if (!employeeId) return;
    setPromotionsLoading(true);
    try {
      const res = await getEmployeePromotions(employeeId);
      setPromotions(res.data || []);
    } catch (err) {
      log.error("Erreur chargement promotions", err);
      setPromotions([]);
    } finally {
      setPromotionsLoading(false);
    }
  }, [employeeId]);

  useEffect(() => {
    if (employeeId) void fetchPromotions();
  }, [employeeId, fetchPromotions]);

  const handleSimulateAugmentation = async () => {
    if (!employeeId || !activeCompanyId) {
      toast({ title: "Entreprise active requise", variant: "destructive" });
      return;
    }
    const v = parseFloat(augValeur.replace(",", "."));
    if (Number.isNaN(v) || v <= 0) {
      toast({ title: "Saisissez une valeur positive.", variant: "destructive" });
      return;
    }
    setAugSimLoading(true);
    try {
      const res = await simulerAugmentation(employeeId, activeCompanyId, {
        type_augmentation: augSimType,
        valeur: v,
        effective_date: augEffectiveDate,
      });
      setAugSimResult(res);
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
      setAugSimLoading(false);
    }
  };

  const handleApplyAugmentationConfirm = async () => {
    if (!employeeId || !activeCompanyId || !augSimResult) return;
    const snapshot = {
      nouveau_brut: augSimResult.nouveau_salaire_brut,
      effective_date: augEffectiveDate,
      motif: augApplyMotif.trim(),
    };
    setAugApplySubmitting(true);
    try {
      await appliquerAugmentation(employeeId, activeCompanyId, {
        nouveau_salaire: augSimResult.nouveau_salaire_brut,
        motif: augApplyMotif.trim() || undefined,
        effective_date: augEffectiveDate,
      });
      toast({
        title: "Augmentation enregistrée",
        description: "Le salaire de base a été mis à jour.",
      });
      setAugApplyDialogOpen(false);
      setAugApplyMotif("");
      setAugSimResult(null);
      setAugValeur("");
      setAugGenDraft(snapshot);
      setAugGenDateInput(snapshot.effective_date);
      setAugGenMotifInput(snapshot.motif);
      await salaryHistoryQuery.refetch();
      const employeeRes = await apiClient.get<Employee>(`/api/employees/${employeeId}`);
      onEmployeeUpdated(employeeRes.data);
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Enregistrement impossible",
        description: typeof msg === "string" ? msg : "Réessayez plus tard.",
        variant: "destructive",
      });
    } finally {
      setAugApplySubmitting(false);
    }
  };

  return (
    <>
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-2 lg:gap-0">
          <div className="space-y-6 min-w-0 lg:pr-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calculator className="h-5 w-5 text-muted-foreground" />
                Augmentation simple
              </CardTitle>
              <CardDescription>
                Salaire brut mensuel :{" "}
                <span className="font-medium text-foreground">
                  {formatEuroAmount(valeurSalaireBrut(employee?.salaire_de_base))}
                </span>
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-3">
                <Label>Type d&apos;augmentation</Label>
                <RadioGroup
                  value={augSimType}
                  onValueChange={(v) => setAugSimType(v as "pourcentage" | "montant_fixe")}
                  className="flex flex-col gap-2 sm:flex-row sm:gap-6"
                >
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="pourcentage" id="aug-pct" />
                    <Label htmlFor="aug-pct" className="font-normal cursor-pointer">
                      Par pourcentage
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="montant_fixe" id="aug-fixe" />
                    <Label htmlFor="aug-fixe" className="font-normal cursor-pointer">
                      Par montant fixe
                    </Label>
                  </div>
                </RadioGroup>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="aug-valeur">
                    {augSimType === "pourcentage" ? "Pourcentage (%)" : "Montant (€)"}
                  </Label>
                  <Input
                    id="aug-valeur"
                    type="number"
                    min={0}
                    step={augSimType === "pourcentage" ? "0.1" : "1"}
                    value={augValeur}
                    onChange={(e) => setAugValeur(e.target.value)}
                    placeholder={augSimType === "pourcentage" ? "Ex. 3" : "Ex. 150"}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="aug-date-effet">Date d&apos;effet</Label>
                  <Input
                    id="aug-date-effet"
                    type="date"
                    value={augEffectiveDate}
                    onChange={(e) => setAugEffectiveDate(e.target.value)}
                  />
                </div>
                <div className="flex items-end">
                  <Button
                    type="button"
                    className="w-full sm:w-auto"
                    onClick={() => void handleSimulateAugmentation()}
                    disabled={augSimLoading || !activeCompanyId}
                  >
                    {augSimLoading ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <TrendingUp className="mr-2 h-4 w-4" />
                    )}
                    Simuler
                  </Button>
                </div>
              </div>

              {augSimResult && (
                <div className="space-y-4">
                  <Card className="border-muted bg-muted/30">
                    <CardContent className="pt-6">
                      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-3">
                        <div className="space-y-2">
                          <p className="text-sm font-semibold">Brut</p>
                          <p className="text-sm text-muted-foreground">
                            Avant : {formatEuroAmount(augSimResult.ancien_salaire_brut)}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            Après : {formatEuroAmount(augSimResult.nouveau_salaire_brut)}
                          </p>
                          <p className="text-sm font-medium text-emerald-700">
                            Gain : +{formatEuroAmount(augSimResult.difference_brut)} (
                            {augSimResult.taux_augmentation_reel.toLocaleString("fr-FR", {
                              maximumFractionDigits: 2,
                            })}
                            %)
                          </p>
                        </div>
                        <div className="space-y-2">
                          <p className="text-sm font-semibold">Net estimé*</p>
                          <p className="text-sm text-muted-foreground">
                            Avant : {formatEuroAmount(augSimResult.ancien_net_estime)}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            Après : {formatEuroAmount(augSimResult.nouveau_net_estime)}
                          </p>
                          <p className="text-sm font-medium text-emerald-700">
                            Gain : +{formatEuroAmount(augSimResult.difference_net)}
                          </p>
                          <p className="text-xs text-muted-foreground leading-snug">
                            * Estimation basée sur des taux moyens. Le net réel figure sur le bulletin de paie.
                          </p>
                        </div>
                        <div className="space-y-2">
                          <p className="text-sm font-semibold">Coût employeur</p>
                          <p className="text-sm text-muted-foreground">
                            Avant : {formatEuroAmount(augSimResult.cout_total_employeur_avant)}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            Après : {formatEuroAmount(augSimResult.cout_total_employeur_apres)}
                          </p>
                          <p className="text-sm font-medium text-emerald-700">
                            Gain : +{formatEuroAmount(augSimResult.difference_cout_employeur)}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  <Button type="button" onClick={() => setAugApplyDialogOpen(true)}>
                    Appliquer cette augmentation
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {augGenDraft && employee && (
            <Card className="border-primary/35 bg-muted/15">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Prochaine étape</CardTitle>
                <CardDescription>
                  Formaliser l&apos;augmentation par un avenant salaire (PDF dans Documents RH).
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap items-center justify-between gap-4">
                <Button
                  type="button"
                  onClick={() => {
                    setAugGenDateInput(augGenDraft.effective_date);
                    setAugGenMotifInput(augGenDraft.motif);
                    setAugGenDialogOpen(true);
                  }}
                >
                  Générer l&apos;avenant salaire
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setAugGenDraft(null)}>
                  Masquer
                </Button>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Historique des augmentations</CardTitle>
              <CardDescription>Évolutions de salaire enregistrées pour ce collaborateur.</CardDescription>
            </CardHeader>
            <CardContent>
              {salaryHistoryQuery.isLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : salaryHistoryQuery.data && salaryHistoryQuery.data.length > 0 ? (
                <div className="w-full overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date d&apos;effet</TableHead>
                        <TableHead>Ancien salaire</TableHead>
                        <TableHead>Nouveau salaire</TableHead>
                        <TableHead>Motif</TableHead>
                        <TableHead>Augmentation</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {salaryHistoryQuery.data.map((row) => {
                        const avant = valeurSalaireBrut(row.ancien_salaire);
                        const apres = valeurSalaireBrut(row.nouveau_salaire);
                        const diff = apres - avant;
                        const pct = avant > 0 ? (diff / avant) * 100 : 0;
                        return (
                          <TableRow key={row.id}>
                            <TableCell>{formatDateFR(row.effective_date)}</TableCell>
                            <TableCell>{formatEuroAmount(avant)}</TableCell>
                            <TableCell>{formatEuroAmount(apres)}</TableCell>
                            <TableCell className="max-w-[200px] truncate" title={row.motif ?? ""}>
                              {row.motif ?? "—"}
                            </TableCell>
                            <TableCell className="font-medium text-emerald-700 whitespace-nowrap">
                              +{formatEuroAmount(diff)} (+
                              {pct.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}%)
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground py-6 text-center">
                  Aucune augmentation enregistrée.
                </p>
              )}
            </CardContent>
          </Card>

          <Dialog open={augApplyDialogOpen} onOpenChange={setAugApplyDialogOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Confirmer l&apos;augmentation</DialogTitle>
                <DialogDescription>
                  Augmenter {employee.first_name} {employee.last_name} de{" "}
                  {augSimResult
                    ? `${formatEuroAmount(augSimResult.ancien_salaire_brut)} à ${formatEuroAmount(
                        augSimResult.nouveau_salaire_brut,
                      )} brut`
                    : ""}
                  .
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-2 py-2">
                <Label htmlFor="aug-motif">Motif (optionnel)</Label>
                <Input
                  id="aug-motif"
                  value={augApplyMotif}
                  onChange={(e) => setAugApplyMotif(e.target.value)}
                  placeholder="Ex. ancienneté, reclassement…"
                />
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setAugApplyDialogOpen(false)}>
                  Annuler
                </Button>
                <Button
                  onClick={() => void handleApplyAugmentationConfirm()}
                  disabled={augApplySubmitting || !augSimResult}
                >
                  {augApplySubmitting ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : null}
                  Confirmer
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Dialog open={augGenDialogOpen} onOpenChange={setAugGenDialogOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Générer un avenant salaire</DialogTitle>
                <DialogDescription>
                  Générer un avenant salaire pour {employee.first_name} {employee.last_name}
                  {augGenDraft ? (
                    <>
                      {" "}
                      — nouveau brut : {formatEuroAmount(augGenDraft.nouveau_brut)}
                    </>
                  ) : null}
                  .
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-2">
                <div className="space-y-2">
                  <Label htmlFor="aug-gen-date">Date d&apos;effet</Label>
                  <Input
                    id="aug-gen-date"
                    type="date"
                    value={augGenDateInput}
                    onChange={(e) => setAugGenDateInput(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="aug-gen-motif">Motif (optionnel)</Label>
                  <Input
                    id="aug-gen-motif"
                    value={augGenMotifInput}
                    onChange={(e) => setAugGenMotifInput(e.target.value)}
                    placeholder="Ex. revue salariale"
                  />
                </div>
                <p className="text-xs text-muted-foreground rounded-md border border-muted bg-muted/30 px-3 py-2">
                  Les données seront enregistrées dans le document pour application automatique lorsque
                  le statut passera à « Signé ».
                </p>
              </div>
              <DialogFooter className="gap-2 sm:gap-0">
                <Button type="button" variant="outline" onClick={() => setAugGenDialogOpen(false)}>
                  Annuler
                </Button>
                <Button
                  type="button"
                  disabled={
                    augSalariatGenMut.isPending ||
                    !employeeId ||
                    !augGenDraft ||
                    !augGenDateInput.trim()
                  }
                  onClick={() => {
                    if (!employeeId || !augGenDraft) return;
                    augSalariatGenMut.mutate({
                      employee_id: employeeId,
                      document_type: "avenant_salaire",
                      category: "avenant",
                      date_effet: augGenDateInput,
                      motif: augGenMotifInput.trim() || undefined,
                      nouveau_salaire: augGenDraft.nouveau_brut,
                      template_id: null,
                    });
                  }}
                >
                  {augSalariatGenMut.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : null}
                  Confirmer
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          </div>

          <div className="space-y-6 min-w-0 lg:border-l-2 lg:border-muted-foreground/35 lg:pl-6">
          <Card>
            <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-4">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Award className="h-5 w-5 text-muted-foreground" />
                  Promotions
                </CardTitle>
                <CardDescription>
                  Évolutions de poste, salaire ou statut pour {employee.first_name} {employee.last_name}.
                </CardDescription>
              </div>
              <Button onClick={() => setPromotionModalOpen(true)} className="shrink-0">
                <Plus className="mr-2 h-4 w-4" />
                Nouvelle promotion
              </Button>
            </CardHeader>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Historique des promotions</CardTitle>
              <CardDescription>
                Promotions et évolutions de carrière enregistrées pour ce collaborateur.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {promotionsLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : promotions.length > 0 ? (
                <div className="w-full overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Type</TableHead>
                        <TableHead>Évolution</TableHead>
                        <TableHead>Date d&apos;effet</TableHead>
                        <TableHead>Statut</TableHead>
                        <TableHead className="w-[100px]">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {promotions.map((promo) => {
                        const evolutionText = [
                          promo.new_job_title,
                          promo.new_salary
                            ? `${promo.new_salary.valeur.toLocaleString("fr-FR")} ${promo.new_salary.devise || "EUR"}`
                            : null,
                          promo.new_statut,
                        ]
                          .filter(Boolean)
                          .join(" • ") || "—";

                        return (
                          <TableRow
                            key={promo.id}
                            className="cursor-pointer hover:bg-muted/50 transition-colors"
                            onClick={() =>
                              navigate(
                                `/promotions/${promo.id}?returnTo=employee&employeeId=${employeeId}&tab=${TAB_AUGMENTATIONS_PROMOTIONS}`
                              )
                            }
                          >
                            <TableCell>
                              <PromotionBadge
                                type={promo.promotion_type}
                                variant="type"
                                compact
                              />
                            </TableCell>
                            <TableCell className="text-muted-foreground">
                              {evolutionText}
                            </TableCell>
                            <TableCell className="text-muted-foreground">
                              {formatDateFR(promo.effective_date)}
                            </TableCell>
                            <TableCell>
                              <PromotionBadge status={promo.status} compact />
                            </TableCell>
                            <TableCell onClick={(e) => e.stopPropagation()}>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() =>
                                  navigate(
                                    `/promotions/${promo.id}?returnTo=employee&employeeId=${employeeId}&tab=${TAB_AUGMENTATIONS_PROMOTIONS}`
                                  )
                                }
                                className="h-8 w-8 p-0"
                                title="Voir les détails"
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground py-6 text-center">
                  Aucune promotion enregistrée.
                </p>
              )}
            </CardContent>
          </Card>
          </div>
          </div>

      <PromotionModal
        isOpen={promotionModalOpen}
        onClose={() => setPromotionModalOpen(false)}
        promotion={null}
        initialEmployeeId={employeeId}
        onSuccess={() => {
          void fetchPromotions();
          setPromotionModalOpen(false);
        }}
      />
    </>
  );
}

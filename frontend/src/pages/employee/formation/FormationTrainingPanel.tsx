import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ExternalLink, FileText, Loader2 } from "lucide-react";

import {
  getEnrollments,
  getTrainings,
  requestEnrollment,
  type TrainingCatalog,
  type TrainingEnrollment,
} from "@/api/training";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { useCompany } from "@/contexts/CompanyContext";
import {
  ENROLLMENT_GROUP_LABELS,
  type EnrollmentGroup,
  enrollmentGroup,
  truncateText,
} from "@/lib/employeeFormationUtils";
import { FormationEnrollmentCard } from "./FormationEnrollmentCard";
import {
  TRAINING_TYPE_LABELS,
  enrollmentHidesTrainingFromCatalogAvailability,
  enrollmentStatusBadge,
  fmtMoney,
} from "./employeeFormationFormatters";

const GROUP_ORDER: EnrollmentGroup[] = ["pending", "active", "done"];

function CatalogTrainingCard({
  t,
  blockingEnrollment,
  onRequest,
}: {
  t: TrainingCatalog;
  blockingEnrollment: TrainingEnrollment | undefined;
  onRequest: (t: TrainingCatalog) => void;
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const hasObjective = Boolean(t.pedagogical_objective?.trim());
  const hasCategories = (t.categories ?? []).length > 0;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base leading-snug">{t.title}</CardTitle>
        <CardDescription className="flex flex-wrap items-center gap-2 pt-1">
          <Badge variant="secondary">
            {TRAINING_TYPE_LABELS[t.training_type] ?? t.training_type}
          </Badge>
          {hasCategories &&
            t.categories.map((c) => (
              <Badge key={c} variant="outline" className="text-xs">
                {c}
              </Badge>
            ))}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {hasObjective && (
          <p className="text-muted-foreground">
            {truncateText(t.pedagogical_objective!.trim(), 160)}
          </p>
        )}
        <p>
          <span className="text-muted-foreground">Organisme : </span>
          {t.provider ?? "—"}
        </p>
        <p>
          <span className="text-muted-foreground">Durée : </span>
          {t.duration_hours != null ? `${t.duration_hours} h` : "—"}
        </p>
        {(t.unit_cost_ht != null || detailsOpen) && (
          <Collapsible open={detailsOpen} onOpenChange={setDetailsOpen}>
            {!detailsOpen && t.unit_cost_ht != null ? (
              <CollapsibleTrigger asChild>
                <Button type="button" variant="link" className="h-auto p-0 text-xs text-muted-foreground">
                  Voir les détails
                  <ChevronDown className="ml-1 h-3 w-3" />
                </Button>
              </CollapsibleTrigger>
            ) : null}
            <CollapsibleContent>
              {t.unit_cost_ht != null && (
                <p className="text-xs text-muted-foreground">
                  Coût HT : {fmtMoney(t.unit_cost_ht)}
                </p>
              )}
            </CollapsibleContent>
          </Collapsible>
        )}
        <div className="flex flex-wrap items-center gap-2 pt-2">
          {blockingEnrollment ? (
            enrollmentStatusBadge(blockingEnrollment.status)
          ) : (
            <Button type="button" size="sm" onClick={() => onRequest(t)}>
              Demander cette formation
            </Button>
          )}
          {t.program_url && (
            <Button variant="outline" size="sm" asChild>
              <a href={t.program_url} target="_blank" rel="noopener noreferrer">
                <FileText className="mr-1 h-4 w-4" />
                Programme PDF
              </a>
            </Button>
          )}
          {t.external_link && (
            <Button variant="ghost" size="sm" asChild>
              <a href={t.external_link} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="mr-1 h-4 w-4" />
                Lien externe
              </a>
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function FormationTrainingPanel({ employeeId }: { employeeId: string }) {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? "";
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [requestOpen, setRequestOpen] = useState(false);
  const [selectedTraining, setSelectedTraining] = useState<TrainingCatalog | null>(null);
  const [prefDate, setPrefDate] = useState("");
  const [motivation, setMotivation] = useState("");

  const enrollQ = useQuery({
    queryKey: ["formation-enrollments", employeeId],
    queryFn: () => getEnrollments({ employee_id: employeeId }),
  });
  const catalogQ = useQuery({
    queryKey: ["formation-catalog-readonly"],
    queryFn: () => getTrainings(false),
  });

  const requestMut = useMutation({
    mutationFn: async () => {
      if (!selectedTraining) throw new Error("missing");
      return requestEnrollment(companyId, {
        training_id: selectedTraining.id,
        preferred_date: prefDate.trim() || undefined,
        motivation: motivation.trim() || undefined,
      });
    },
    onSuccess: () => {
      toast({ title: "Demande envoyée — en attente de validation" });
      setRequestOpen(false);
      setSelectedTraining(null);
      setPrefDate("");
      setMotivation("");
      void queryClient.invalidateQueries({ queryKey: ["formation-enrollments", employeeId] });
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Impossible d'envoyer la demande.";
      toast({ title: "Erreur", description: String(detail), variant: "destructive" });
    },
  });

  const catalogById = useMemo(() => {
    const m = new Map<string, TrainingCatalog>();
    for (const t of catalogQ.data ?? []) m.set(t.id, t);
    return m;
  }, [catalogQ.data]);

  const catalogTrainings = catalogQ.data ?? [];

  const blockingEnrollmentByTrainingId = useMemo(() => {
    const cats = catalogQ.data ?? [];
    const rows = enrollQ.data ?? [];
    const m = new Map<string, TrainingEnrollment>();
    for (const t of cats) {
      const reps = rows.filter(
        (e) => e.training_id === t.id && enrollmentHidesTrainingFromCatalogAvailability(e.status),
      );
      if (!reps.length) continue;
      reps.sort((a, b) => {
        const ta = new Date(a.updated_at || a.created_at || 0).getTime();
        const tb = new Date(b.updated_at || b.created_at || 0).getTime();
        return tb - ta;
      });
      m.set(t.id, reps[0]!);
    }
    return m;
  }, [catalogQ.data, enrollQ.data]);

  const enrollmentsByGroup = useMemo(() => {
    const groups: Record<EnrollmentGroup, TrainingEnrollment[]> = {
      pending: [],
      active: [],
      done: [],
    };
    for (const e of enrollQ.data ?? []) {
      groups[enrollmentGroup(e.status)].push(e);
    }
    return groups;
  }, [enrollQ.data]);

  const catalogAllUnavailable =
    catalogTrainings.length > 0 &&
    catalogTrainings.every((t) => blockingEnrollmentByTrainingId.has(t.id));

  const openRequest = (t: TrainingCatalog) => {
    setSelectedTraining(t);
    setPrefDate("");
    setMotivation("");
    setRequestOpen(true);
  };

  if (!companyId) {
    return (
      <p className="text-sm text-muted-foreground">Sélectionnez une entreprise pour gérer vos formations.</p>
    );
  }

  return (
    <div className="space-y-10">
      <Dialog open={requestOpen} onOpenChange={setRequestOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Demander une inscription</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <p className="text-sm text-muted-foreground">Formation</p>
              <p className="font-medium">{selectedTraining?.title ?? "—"}</p>
            </div>
            <div className="space-y-1.5">
              <label htmlFor="pref-date" className="text-sm font-medium">
                Date souhaitée <span className="font-normal text-muted-foreground">(optionnel)</span>
              </label>
              <Input
                id="pref-date"
                type="date"
                value={prefDate}
                onChange={(e) => setPrefDate(e.target.value)}
                className="w-full"
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="motivation" className="text-sm font-medium">
                Motivation <span className="font-normal text-muted-foreground">(optionnel)</span>
              </label>
              <Textarea
                id="motivation"
                value={motivation}
                onChange={(e) => setMotivation(e.target.value)}
                rows={3}
                placeholder="Précisez le contexte ou vos attentes…"
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setRequestOpen(false)}>
              Annuler
            </Button>
            <Button
              type="button"
              disabled={requestMut.isPending || !selectedTraining}
              onClick={() => requestMut.mutate()}
            >
              {requestMut.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Envoi…
                </>
              ) : (
                "Confirmer"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Mes inscriptions</h2>
        {enrollQ.isLoading ? (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            Chargement…
          </div>
        ) : enrollQ.isError ? (
          <p className="text-sm text-destructive">Impossible de charger vos inscriptions.</p>
        ) : (enrollQ.data ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune inscription à une formation.</p>
        ) : (
          <div className="space-y-8">
            {GROUP_ORDER.map((groupKey) => {
              const items = enrollmentsByGroup[groupKey];
              if (items.length === 0) return null;
              return (
                <div key={groupKey} className="space-y-3">
                  <h3 className="text-sm font-medium text-muted-foreground">
                    {ENROLLMENT_GROUP_LABELS[groupKey]}
                  </h3>
                  <div className="space-y-4">
                    {items.map((e) => (
                      <FormationEnrollmentCard
                        key={e.id}
                        e={e}
                        cat={catalogById.get(e.training_id)}
                        companyId={companyId}
                        employeeId={employeeId}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Catalogue</h2>
        {catalogQ.isLoading ? (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            Chargement…
          </div>
        ) : catalogQ.isError ? (
          <p className="text-sm text-destructive">Impossible de charger le catalogue.</p>
        ) : catalogTrainings.length === 0 ? (
          <p className="rounded-md border border-dashed bg-muted/30 px-4 py-8 text-center text-sm text-muted-foreground">
            Aucune formation proposée par votre entreprise pour le moment.
          </p>
        ) : catalogAllUnavailable ? (
          <p className="rounded-md border border-dashed bg-muted/30 px-4 py-8 text-center text-sm text-muted-foreground">
            Vous avez suivi toutes les formations disponibles.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {catalogTrainings.map((t) => (
              <CatalogTrainingCard
                key={t.id}
                t={t}
                blockingEnrollment={blockingEnrollmentByTrainingId.get(t.id)}
                onRequest={openRequest}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

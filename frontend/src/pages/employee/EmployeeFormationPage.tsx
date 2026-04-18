// Page collaborateur unifiée « Ma formation » (Pack Talent T10) — lecture seule

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Check, ChevronDown, ExternalLink, FileText, Loader2, X } from "lucide-react";

import { getObjectives, type EmployeeObjective } from "@/api/objectives";
import { getEmployeeCertifications, type ComputedStatus, type EmployeeCertification } from "@/api/certifications";
import { getEnrollments, getTrainings, type TrainingCatalog, type TrainingEnrollment } from "@/api/training";
import {
  getEmployeeStatus,
  type LegalObligationStatus,
  type ProfessionalInterviewStatus,
} from "@/api/legalObligations";
import { getEvaluations, type EmployeeCompetency } from "@/api/competencies";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useCompany } from "@/contexts/CompanyContext";
import { useCurrentEmployee } from "@/hooks/useCurrentEmployee";
import { cn } from "@/lib/utils";

import EmployeeAnnualReviews from "@/pages/employee/AnnualReviews";

const TRAINING_TYPE_LABELS: Record<string, string> = {
  presentiel: "Présentiel",
  distanciel: "Distanciel",
  elearning: "E-learning",
  blended: "Blended",
  habilitation: "Habilitation",
};

function fmtDate(s?: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("fr-FR");
}

function fmtMoney(n?: number | null) {
  if (n == null || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(n);
}

function objectiveStatusBadge(status: string) {
  const cfg: Record<string, { label: string; className: string }> = {
    draft: { label: "Brouillon", className: "bg-muted text-muted-foreground" },
    active: { label: "Actif", className: "bg-blue-600 text-white hover:bg-blue-600" },
    achieved: { label: "Atteint", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    partially_achieved: {
      label: "Partiellement atteint",
      className: "bg-orange-500 text-white hover:bg-orange-500",
    },
    not_achieved: { label: "Non atteint", className: "bg-red-600 text-white hover:bg-red-600" },
    cancelled: { label: "Annulé", className: "bg-muted text-muted-foreground" },
  };
  const x = cfg[status] ?? { label: status, className: "bg-muted text-muted-foreground" };
  return <Badge className={x.className}>{x.label}</Badge>;
}

function objectiveTypeBadge(t: string) {
  const qual = t === "qualitative";
  return (
    <Badge variant="outline" className={qual ? "border-violet-500 text-violet-700" : "border-sky-500 text-sky-700"}>
      {qual ? "Qualitatif" : "Quantitatif"}
    </Badge>
  );
}

function certStatusBadge(status: ComputedStatus) {
  const cfg: Record<ComputedStatus, { label: string; className: string }> = {
    valid: { label: "Valide", className: "border-0 bg-emerald-600 text-white hover:bg-emerald-600" },
    expiring_soon: {
      label: "Expire bientôt",
      className: "border-0 bg-orange-500 text-white hover:bg-orange-500",
    },
    expired: { label: "Expiré", className: "border-0 bg-red-600 text-white hover:bg-red-600" },
    no_expiry: {
      label: "Sans expiration",
      className: "border-0 bg-muted text-muted-foreground hover:bg-muted",
    },
  };
  const x = cfg[status];
  return <Badge className={x.className}>{x.label}</Badge>;
}

function enrollmentStatusBadge(status: string) {
  const s = status.toLowerCase();
  const cfg: Record<string, { label: string; className: string }> = {
    planned: { label: "Planifié", className: "bg-blue-600 text-white hover:bg-blue-600" },
    in_progress: { label: "En cours", className: "bg-orange-500 text-white hover:bg-orange-500" },
    completed: { label: "Terminé", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    cancelled: { label: "Annulé", className: "bg-muted text-muted-foreground" },
  };
  const x = cfg[s] ?? { label: status, className: "bg-muted text-muted-foreground" };
  return <Badge className={x.className}>{x.label}</Badge>;
}

function profBadge(st: ProfessionalInterviewStatus) {
  const map: Record<ProfessionalInterviewStatus, { label: string; className: string }> = {
    up_to_date: { label: "À jour", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    due_soon: { label: "Échéance proche", className: "bg-amber-600 text-white hover:bg-amber-600" },
    overdue: { label: "En retard", className: "bg-red-600 text-white hover:bg-red-600" },
    unknown: { label: "Non calculable", className: "bg-muted text-muted-foreground" },
  };
  const x = map[st];
  return <Badge className={x.className}>{x.label}</Badge>;
}

function sixBadge(st: LegalObligationStatus["six_year_review_status"]) {
  const map: Record<
    LegalObligationStatus["six_year_review_status"],
    { label: string; className: string }
  > = {
    validated: { label: "Validé", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    in_progress: { label: "En cours", className: "bg-sky-600 text-white hover:bg-sky-600" },
    not_validated: { label: "Non validé", className: "bg-red-600 text-white hover:bg-red-600" },
    unknown: { label: "Non calculable", className: "bg-muted text-muted-foreground" },
  };
  const x = map[st];
  return <Badge className={x.className}>{x.label}</Badge>;
}

function CriterionReadOnly({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {ok ? (
        <Check className="h-4 w-4 shrink-0 text-emerald-600" aria-hidden />
      ) : (
        <X className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
      )}
      <span className={ok ? "" : "text-muted-foreground"}>{label}</span>
    </div>
  );
}

function competencyScoreBadge(score: number) {
  const map: Record<number, { label: string; className: string }> = {
    0: { label: "Non évalué", className: "bg-neutral-200 text-neutral-700" },
    1: { label: "Notions de base", className: "bg-red-600 text-white hover:bg-red-600" },
    2: { label: "Opérationnel", className: "bg-orange-500 text-white hover:bg-orange-500" },
    3: { label: "Maîtrise", className: "bg-green-200 text-green-900" },
    4: { label: "Expert", className: "bg-green-700 text-white hover:bg-green-700" },
  };
  const x = map[score] ?? map[0];
  return <Badge className={cn("border-0", x.className)}>{x.label}</Badge>;
}

function categoryLabelFr(cat?: string | null) {
  if (!cat) return "—";
  const m: Record<string, string> = {
    technique: "Technique",
    managériale: "Managériale",
    transversale: "Transversale",
    réglementaire: "Réglementaire",
    sécurité: "Sécurité",
  };
  return m[cat] ?? cat;
}

function sortObjectivesByDue(list: EmployeeObjective[]) {
  return [...list].sort((a, b) => {
    if (!a.due_date && !b.due_date) return 0;
    if (!a.due_date) return 1;
    if (!b.due_date) return -1;
    return new Date(a.due_date).getTime() - new Date(b.due_date).getTime();
  });
}

function latestActualFromMilestones(obj: EmployeeObjective): number | null {
  const sorted = [...obj.milestones].sort(
    (m1, m2) => new Date(m1.milestone_date).getTime() - new Date(m2.milestone_date).getTime(),
  );
  for (let i = sorted.length - 1; i >= 0; i -= 1) {
    const v = sorted[i].actual_value;
    if (v != null && !Number.isNaN(Number(v))) return Number(v);
  }
  return null;
}

function FormationObjectivesPanel({ employeeId }: { employeeId: string }) {
  const currentCalendarYear = new Date().getFullYear();
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyYear, setHistoryYear] = useState(Math.max(currentCalendarYear - 1, 2000));

  const pastYears = useMemo(() => {
    const ys: number[] = [];
    for (let y = currentCalendarYear - 1; y >= currentCalendarYear - 15 && y >= 2000; y -= 1) ys.push(y);
    return ys;
  }, [currentCalendarYear]);

  const currentQuery = useQuery({
    queryKey: ["formation-objectives", employeeId, currentCalendarYear],
    queryFn: () =>
      getObjectives({ employee_id: employeeId, period_year: currentCalendarYear, include_inactive: true }),
  });

  const historyQuery = useQuery({
    queryKey: ["formation-objectives", employeeId, "history", historyYear],
    queryFn: () =>
      getObjectives({ employee_id: employeeId, period_year: historyYear, include_inactive: true }),
    enabled: historyOpen,
  });

  const renderObjectiveCard = (obj: EmployeeObjective) => {
    const isQuant = obj.type === "quantitative";
    const sortedMilestones = [...obj.milestones].sort(
      (a, b) => new Date(a.milestone_date).getTime() - new Date(b.milestone_date).getTime(),
    );
    const chartData = sortedMilestones.map((m) => ({
      label: fmtDate(m.milestone_date),
      attendu: m.expected_value,
      reel: m.actual_value != null ? Number(m.actual_value) : null,
    }));
    const latestActual = latestActualFromMilestones(obj);
    const sortedCheckins = [...obj.checkins].sort(
      (a, b) => new Date(a.checkin_date).getTime() - new Date(b.checkin_date).getTime(),
    );

    return (
      <Card key={obj.id}>
        <CardHeader className="pb-2">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <CardTitle className="text-base font-semibold leading-snug">{obj.title}</CardTitle>
            <div className="flex flex-wrap gap-2">
              {objectiveTypeBadge(String(obj.type))}
              {objectiveStatusBadge(String(obj.status))}
            </div>
          </div>
          <CardDescription className="flex flex-wrap gap-x-4 gap-y-1 pt-1">
            {obj.due_date && <span>Échéance : {fmtDate(obj.due_date)}</span>}
            {obj.weight != null && <span>Pondération : {obj.weight}</span>}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {isQuant && (
            <div className="space-y-2">
              <p>
                <span className="text-muted-foreground">Valeur cible : </span>
                {obj.kpi_target_value != null ? `${obj.kpi_target_value}${obj.kpi_unit ? ` ${obj.kpi_unit}` : ""}` : "—"}
                {obj.kpi_label ? ` (${obj.kpi_label})` : ""}
              </p>
              <p>
                <span className="text-muted-foreground">Valeur actuelle (dernier point saisi) : </span>
                {latestActual != null ? `${latestActual}${obj.kpi_unit ? ` ${obj.kpi_unit}` : ""}` : "—"}
              </p>
              {chartData.length > 0 ? (
                <div className="h-56 w-full min-w-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Legend />
                      <Line type="monotone" dataKey="attendu" name="Attendu" stroke="#64748b" dot={false} />
                      <Line type="monotone" dataKey="reel" name="Réel" stroke="#2563eb" connectNulls />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="text-muted-foreground">Aucun jalon défini pour suivre la courbe attendu / réel.</p>
              )}
            </div>
          )}

          {!isQuant && (
            <div>
              <p className="mb-2 font-medium text-foreground">Suivi qualitatif</p>
              {sortedCheckins.length === 0 ? (
                <p className="text-muted-foreground">Aucun point d&apos;étape enregistré.</p>
              ) : (
                <ul className="space-y-2 border-l-2 border-muted pl-3">
                  {sortedCheckins.map((c) => (
                    <li key={c.id} className="text-sm">
                      <span className="text-muted-foreground">{fmtDate(c.checkin_date)}</span>
                      <p className="mt-0.5 whitespace-pre-wrap">{c.progress_note}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {(obj.final_achievement_rate != null || obj.evaluation_comment) && (
            <div className="rounded-md border bg-muted/30 p-3">
              {obj.final_achievement_rate != null && (
                <p>
                  <span className="text-muted-foreground">Taux d&apos;atteinte final : </span>
                  {obj.final_achievement_rate}%
                </p>
              )}
              {obj.evaluation_comment && (
                <p className="mt-1">
                  <span className="text-muted-foreground">Commentaire RH : </span>
                  {obj.evaluation_comment}
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  const renderYearBlock = (
    year: number,
    q: typeof currentQuery,
    emptyHint: string,
  ) => {
    if (q.isLoading) {
      return (
        <div className="flex items-center gap-2 py-8 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          Chargement…
        </div>
      );
    }
    if (q.isError) {
      return <p className="text-sm text-destructive">Impossible de charger vos objectifs.</p>;
    }
    const list = sortObjectivesByDue(q.data ?? []);
    if (list.length === 0) {
      return <p className="py-6 text-center text-sm text-muted-foreground">{emptyHint}</p>;
    }
    return <div className="space-y-4">{list.map((o) => renderObjectiveCard(o))}</div>;
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Objectifs {currentCalendarYear}</h2>
        <p className="text-sm text-muted-foreground">Vue synthétique en lecture seule.</p>
      </div>
      {renderYearBlock(
        currentCalendarYear,
        currentQuery,
        `Vos objectifs pour ${currentCalendarYear} seront affichés ici dès qu'ils auront été définis par votre responsable RH.`,
      )}

      {pastYears.length > 0 && (
        <Collapsible open={historyOpen} onOpenChange={setHistoryOpen}>
          <CollapsibleTrigger asChild>
            <Button variant="outline" className="w-full justify-between sm:w-auto">
              Années précédentes
              <ChevronDown
                className={cn("ml-2 h-4 w-4 transition-transform", historyOpen && "rotate-180")}
              />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-4 space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm text-muted-foreground">Année</span>
              <Select
                value={String(historyYear)}
                onValueChange={(v) => setHistoryYear(Number.parseInt(v, 10))}
              >
                <SelectTrigger className="w-[140px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {pastYears.map((y) => (
                    <SelectItem key={y} value={String(y)}>
                      {y}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {renderYearBlock(
              historyYear,
              historyQuery,
              `Vos objectifs pour ${historyYear} seront affichés ici dès qu'ils auront été définis par votre responsable RH.`,
            )}
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
}

function FormationCertificationsPanel({ employeeId }: { employeeId: string }) {
  const q = useQuery({
    queryKey: ["formation-certs", employeeId],
    queryFn: () => getEmployeeCertifications({ employee_id: employeeId, include_archived: false }),
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 py-8 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        Chargement…
      </div>
    );
  }
  if (q.isError) {
    return <p className="text-sm text-destructive">Impossible de charger vos habilitations.</p>;
  }
  const rows = q.data ?? [];
  if (rows.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Aucune habilitation enregistrée pour votre profil.
      </p>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Habilitation</TableHead>
            <TableHead>Obtention</TableHead>
            <TableHead>Expiration</TableHead>
            <TableHead>Statut</TableHead>
            <TableHead className="text-right">Certificat</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r: EmployeeCertification) => (
            <TableRow key={r.id}>
              <TableCell className="font-medium">
                {r.certification_ref?.name ?? "—"}
              </TableCell>
              <TableCell>{fmtDate(r.obtained_date)}</TableCell>
              <TableCell>{r.expiry_date ? fmtDate(r.expiry_date) : "—"}</TableCell>
              <TableCell>{certStatusBadge(r.computed_status)}</TableCell>
              <TableCell className="text-right">
                {r.certificate_url ? (
                  <Button variant="outline" size="sm" asChild>
                    <a href={r.certificate_url} target="_blank" rel="noopener noreferrer">
                      Voir certificat
                    </a>
                  </Button>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function FormationTrainingPanel({ employeeId }: { employeeId: string }) {
  const enrollQ = useQuery({
    queryKey: ["formation-enrollments", employeeId],
    queryFn: () => getEnrollments({ employee_id: employeeId }),
  });
  const catalogQ = useQuery({
    queryKey: ["formation-catalog-readonly"],
    queryFn: () => getTrainings(false),
  });

  const catalogById = useMemo(() => {
    const m = new Map<string, TrainingCatalog>();
    for (const t of catalogQ.data ?? []) m.set(t.id, t);
    return m;
  }, [catalogQ.data]);

  return (
    <div className="space-y-10">
      <section className="space-y-3">
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
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Formation</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Date planifiée</TableHead>
                  <TableHead>Statut</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(enrollQ.data ?? []).map((e: TrainingEnrollment) => {
                  const cat = catalogById.get(e.training_id);
                  const typeLabel = cat?.training_type
                    ? TRAINING_TYPE_LABELS[cat.training_type] ?? cat.training_type
                    : "—";
                  return (
                    <TableRow key={e.id}>
                      <TableCell className="font-medium">{e.training_title ?? cat?.title ?? "—"}</TableCell>
                      <TableCell>{typeLabel}</TableCell>
                      <TableCell>{e.planned_date ? fmtDate(e.planned_date) : "—"}</TableCell>
                      <TableCell>{enrollmentStatusBadge(e.status)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
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
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {(catalogQ.data ?? []).map((t: TrainingCatalog) => (
              <Card key={t.id}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base leading-snug">{t.title}</CardTitle>
                  <CardDescription>
                    <Badge variant="secondary" className="mt-1">
                      {TRAINING_TYPE_LABELS[t.training_type] ?? t.training_type}
                    </Badge>
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <p>
                    <span className="text-muted-foreground">Organisme : </span>
                    {t.provider ?? "—"}
                  </p>
                  <p>
                    <span className="text-muted-foreground">Durée : </span>
                    {t.duration_hours != null ? `${t.duration_hours} h` : "—"}
                  </p>
                  <p>
                    <span className="text-muted-foreground">Coût HT : </span>
                    {fmtMoney(t.unit_cost_ht)}
                  </p>
                  <div className="flex flex-wrap gap-2 pt-2">
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
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function FormationLegalPanel({ employeeId }: { employeeId: string }) {
  const q = useQuery({
    queryKey: ["formation-legal", employeeId],
    queryFn: () => getEmployeeStatus(employeeId),
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 py-8 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        Chargement…
      </div>
    );
  }
  if (q.isError || !q.data) {
    return <p className="text-sm text-destructive">Impossible de charger vos obligations légales.</p>;
  }
  const s = q.data;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Entretien professionnel (2 ans)</CardTitle>
          <CardDescription>Suivi réglementaire en lecture seule.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div>{profBadge(s.professional_interview_status)}</div>
          <p>
            {s.last_professional_interview_date ? (
              <>
                <span className="text-muted-foreground">Dernier entretien : </span>
                {fmtDate(s.last_professional_interview_date)}
              </>
            ) : (
              <span className="text-muted-foreground">Aucun entretien enregistré</span>
            )}
          </p>
          <p>
            <span className="text-muted-foreground">Prochain entretien avant : </span>
            {fmtDate(s.professional_interview_next_due)}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Bilan de compétences (6 ans)</CardTitle>
          <CardDescription>Critères cumulés sur la période.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div>{sixBadge(s.six_year_review_status)}</div>
          <p>
            <span className="text-muted-foreground">Échéance : </span>
            {fmtDate(s.six_year_next_due)}
          </p>
          <div className="space-y-2 border-t pt-3">
            <CriterionReadOnly ok={s.criteria_training_completed} label="Formation non obligatoire suivie" />
            <CriterionReadOnly ok={s.criteria_certification_obtained} label="Certification obtenue" />
            <CriterionReadOnly ok={s.criteria_career_evolution} label="Évolution salariale ou professionnelle" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function FormationCompetenciesPanel({ employeeId }: { employeeId: string }) {
  const q = useQuery({
    queryKey: ["formation-competencies", employeeId],
    queryFn: () => getEvaluations(employeeId),
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 py-8 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        Chargement…
      </div>
    );
  }
  if (q.isError) {
    return <p className="text-sm text-destructive">Impossible de charger vos compétences.</p>;
  }
  const rows = q.data ?? [];
  if (rows.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Vos compétences n&apos;ont pas encore été évaluées.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {rows.map((e: EmployeeCompetency) => (
        <Card key={e.id}>
          <CardHeader className="pb-2">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <CardTitle className="text-base">{e.competency_name ?? "Compétence"}</CardTitle>
                <CardDescription>{categoryLabelFr(e.competency_category)}</CardDescription>
              </div>
              {competencyScoreBadge(e.score)}
            </div>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {e.required_level != null && (
              <p>
                <span className="text-muted-foreground">Niveau requis : </span>
                {e.required_level}
              </p>
            )}
            {e.is_gap && (
              <Badge variant="destructive" className="border-0">
                En dessous du niveau requis
              </Badge>
            )}
            <p className="text-muted-foreground">Évaluation : {fmtDate(e.evaluation_date)}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function EmployeeFormationPage() {
  const { activeCompany } = useCompany();
  const { employee, isLoading, isError, notConfigured, error, refetch } = useCurrentEmployee();

  if (!activeCompany?.company_id) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          Sélectionnez une entreprise pour afficher votre espace formation.
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin" />
        <p className="text-sm">Chargement de votre profil…</p>
      </div>
    );
  }

  if (isError) {
    const msg =
      (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
      "Une erreur est survenue.";
    return (
      <Card className="border-destructive/40">
        <CardContent className="flex flex-col gap-3 py-6 text-sm">
          <p className="text-destructive">{msg}</p>
          <Button variant="outline" size="sm" className="w-fit" onClick={() => void refetch()}>
            Réessayer
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (notConfigured || !employee) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          Votre profil collaborateur n&apos;est pas encore configuré. Contactez votre service RH.
        </CardContent>
      </Card>
    );
  }

  const employeeId = employee.id;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Ma formation</h1>
        <p className="mt-2 text-muted-foreground">
          Entretiens, objectifs, habilitations, formations et obligations légales — consultation uniquement.
        </p>
      </div>

      <Tabs defaultValue="entretiens" className="w-full">
        <TabsList className="mb-4 flex h-auto w-full flex-wrap justify-start gap-1">
          <TabsTrigger value="entretiens">Mes entretiens</TabsTrigger>
          <TabsTrigger value="objectifs">Mes objectifs</TabsTrigger>
          <TabsTrigger value="habilitations">Mes habilitations</TabsTrigger>
          <TabsTrigger value="formations">Mes formations</TabsTrigger>
          <TabsTrigger value="obligations">Obligations légales</TabsTrigger>
          <TabsTrigger value="competences">Mes compétences</TabsTrigger>
        </TabsList>

        <TabsContent value="entretiens" className="mt-0">
          <EmployeeAnnualReviews embedded />
        </TabsContent>

        <TabsContent value="objectifs" className="mt-0">
          <FormationObjectivesPanel employeeId={employeeId} />
        </TabsContent>

        <TabsContent value="habilitations" className="mt-0">
          <FormationCertificationsPanel employeeId={employeeId} />
        </TabsContent>

        <TabsContent value="formations" className="mt-0">
          <FormationTrainingPanel employeeId={employeeId} />
        </TabsContent>

        <TabsContent value="obligations" className="mt-0">
          <FormationLegalPanel employeeId={employeeId} />
        </TabsContent>

        <TabsContent value="competences" className="mt-0">
          <FormationCompetenciesPanel employeeId={employeeId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

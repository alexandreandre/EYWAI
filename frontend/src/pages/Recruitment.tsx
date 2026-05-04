// frontend/src/pages/Recruitment.tsx
// Page RH : Module Recrutement (ATS) — Pipeline Kanban + Vue Liste + Fiche candidat

import { useState, useMemo, useRef, useCallback, useEffect, type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getJobs, createJob, getPipelineStages, getCandidates, createCandidate,
  moveCandidate, getNotes, createNote, uploadNoteAudio, getOpinions, createOpinion,
  getInterviews, createInterview, getTimeline, hireCandidate, getRejectionReasons,
  checkDuplicate,
  createPipelineStage, updatePipelineStage, deletePipelineStage, reorderPipelineStages,
  uploadCandidateCV, updateInterview,
  scoreCandidateAI, getCandidateScore,
  getRecruitmentAnalytics,
  type Job, type PipelineStage, type Candidate, type Note, type Opinion,
  type Interview, type HireResult, type ScoringResult,
  type RecruitmentAnalyticsParams, type RecruitmentAnalytics,
} from "@/api/recruitment";
import apiClient from "@/api/apiClient";
import { listCompanyServices } from "@/api/objectives";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useToast } from "@/components/ui/use-toast";
import {
  Plus, Search, LayoutGrid, List, User, Mail, Phone, Calendar,
  Clock, MapPin, Link2, FileText, ThumbsUp, ThumbsDown,
  Loader2, Briefcase, X, ChevronRight, MessageSquare, AlertTriangle,
  UserPlus, Check, GripVertical, Sparkles, RefreshCw, CheckCircle2, AlertCircle,
  BarChart3, Mic, Square, Trash2,
} from "lucide-react";
import {
  DndContext,
  DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  horizontalListSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { cn } from "@/lib/utils";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";

function recruitmentAiPalette(score: number) {
  if (score >= 80) {
    return {
      bar: "bg-emerald-600",
      badge: "bg-emerald-600 text-white border-emerald-700 shadow-sm",
    };
  }
  if (score >= 60) {
    return {
      bar: "bg-blue-600",
      badge: "bg-blue-600 text-white border-blue-700 shadow-sm",
    };
  }
  if (score >= 40) {
    return {
      bar: "bg-orange-500",
      badge: "bg-orange-500 text-white border-orange-600 shadow-sm",
    };
  }
  return {
    bar: "bg-red-600",
    badge: "bg-red-600 text-white border-red-700 shadow-sm",
  };
}

const eurFmt = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

// ─── Analytics (RH) ─────────────────────────────────────────────────

function RecruitmentAnalyticsSection({
  companyId,
  jobs,
}: {
  companyId: string;
  jobs: Job[];
}) {
  const [formJobId, setFormJobId] = useState("__all__");
  const [formDateFrom, setFormDateFrom] = useState("");
  const [formDateTo, setFormDateTo] = useState("");
  const [formBudget, setFormBudget] = useState("");
  const [queryParams, setQueryParams] = useState<RecruitmentAnalyticsParams>({});

  useEffect(() => {
    setFormJobId("__all__");
    setFormDateFrom("");
    setFormDateTo("");
    setFormBudget("");
    setQueryParams({});
  }, [companyId]);

  const commitFilters = useCallback(() => {
    const p: RecruitmentAnalyticsParams = {};
    if (formJobId && formJobId !== "__all__") p.job_id = formJobId;
    if (formDateFrom.trim()) p.date_from = formDateFrom.trim();
    if (formDateTo.trim()) p.date_to = formDateTo.trim();
    const raw = formBudget.trim().replace(/\s/g, "").replace(",", ".");
    if (raw) {
      const n = parseFloat(raw);
      if (!Number.isNaN(n)) p.budget_total = n;
    }
    setQueryParams(p);
  }, [formJobId, formDateFrom, formDateTo, formBudget]);

  const { data: analyticsData, isLoading, isFetching } = useQuery({
    queryKey: ["recruitment", "analytics", companyId, queryParams],
    queryFn: () => getRecruitmentAnalytics(companyId, queryParams),
    enabled: Boolean(companyId),
  });

  const loading = isLoading || isFetching;
  const d = analyticsData;
  const showCostCard = d != null && d.cost_per_hire != null;

  const sourceChartData = useMemo(
    () =>
      (d?.source_stats ?? []).map((s) => ({
        source: s.source.length > 28 ? `${s.source.slice(0, 28)}…` : s.source,
        fullSource: s.source,
        candidats: s.nb_candidates,
        embauches: s.nb_hired,
      })),
    [d?.source_stats],
  );

  const stageChartData = useMemo(
    () =>
      (d?.stage_conversion ?? []).map((s) => ({
        name: s.stage_name.length > 36 ? `${s.stage_name.slice(0, 36)}…` : s.stage_name,
        fullName: s.stage_name,
        candidats: s.nb_candidates,
        conversion: Math.round(s.conversion_rate * 10) / 10,
      })),
    [d?.stage_conversion],
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">Filtres</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 lg:flex-row lg:flex-wrap lg:items-end">
          <div className="space-y-2 min-w-[200px]">
            <Label>Poste</Label>
            <Select value={formJobId} onValueChange={setFormJobId}>
              <SelectTrigger className="w-[260px]">
                <SelectValue placeholder="Poste" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">Tous les postes</SelectItem>
                {jobs.map((j) => (
                  <SelectItem key={j.id} value={j.id}>
                    {j.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="an-date-from">Du</Label>
            <Input
              id="an-date-from"
              type="date"
              className="w-[180px]"
              value={formDateFrom}
              onChange={(e) => setFormDateFrom(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="an-date-to">Au</Label>
            <Input
              id="an-date-to"
              type="date"
              className="w-[180px]"
              value={formDateTo}
              onChange={(e) => setFormDateTo(e.target.value)}
            />
          </div>
          <div className="space-y-2 flex-1 min-w-[160px] max-w-xs">
            <Label htmlFor="an-budget">Budget recrutement (€)</Label>
            <Input
              id="an-budget"
              inputMode="decimal"
              placeholder="Optionnel"
              value={formBudget}
              onChange={(e) => setFormBudget(e.target.value)}
            />
          </div>
          <Button type="button" onClick={commitFilters} disabled={!companyId} className="lg:mb-0.5">
            <RefreshCw className="h-4 w-4 mr-2" />
            Actualiser
          </Button>
        </CardContent>
      </Card>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
      ) : (
        <>
          <div className={cn("grid gap-4 sm:grid-cols-2", showCostCard ? "lg:grid-cols-5" : "lg:grid-cols-4")}>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm font-medium text-muted-foreground">Total candidatures</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold tabular-nums">{d?.total_candidates ?? 0}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm font-medium text-muted-foreground">Total embauches</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold tabular-nums">{d?.total_hired ?? 0}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm font-medium text-muted-foreground">Taux de conversion global</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold tabular-nums">
                  {(d?.overall_conversion_rate ?? 0).toFixed(1)}%
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm font-medium text-muted-foreground">Temps moyen d&apos;embauche</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold tabular-nums">
                  {(d?.avg_time_to_hire_days ?? 0).toFixed(1)}
                  <span className="text-base font-normal text-muted-foreground ml-1">j</span>
                </p>
              </CardContent>
            </Card>
            {showCostCard && d?.cost_per_hire != null ? (
              <Card>
                <CardHeader className="pb-1">
                  <CardTitle className="text-sm font-medium text-muted-foreground">Coût par embauche</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold tabular-nums">{eurFmt.format(d.cost_per_hire)}</p>
                </CardContent>
              </Card>
            ) : null}
          </div>

          <div className="grid gap-6 lg:grid-cols-1">
            <Card>
              <CardHeader>
                <CardTitle>Efficacité des sources</CardTitle>
                <p className="text-sm text-muted-foreground">Candidatures vs embauches par canal</p>
              </CardHeader>
              <CardContent>
                {!sourceChartData.length ? (
                  <p className="text-sm text-muted-foreground py-8 text-center">Aucune donnée</p>
                ) : (
                  <ResponsiveContainer width="100%" height={Math.max(220, sourceChartData.length * 40)}>
                    <BarChart
                      layout="vertical"
                      data={sourceChartData}
                      margin={{ top: 8, right: 24, left: 8, bottom: 8 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis type="number" allowDecimals={false} className="text-xs" />
                      <YAxis dataKey="source" type="category" width={100} tick={{ fontSize: 11 }} />
                      <RechartsTooltip
                        content={({ active, payload }) => {
                          if (!active || !payload?.length) return null;
                          const p = payload[0].payload as {
                            fullSource?: string;
                            candidats?: number;
                            embauches?: number;
                          };
                          return (
                            <div className="rounded-md border bg-background px-2 py-1.5 text-xs shadow-md">
                              <p className="font-medium mb-1">{p.fullSource}</p>
                              <p className="text-muted-foreground">Candidats : {p.candidats}</p>
                              <p className="text-muted-foreground">Embauches : {p.embauches}</p>
                            </div>
                          );
                        }}
                      />
                      <Legend />
                      <Bar dataKey="candidats" name="Candidats" fill="#94a3b8" radius={[0, 4, 4, 0]} />
                      <Bar dataKey="embauches" name="Embauches" fill="#22c55e" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Conversion par étape</CardTitle>
                <p className="text-sm text-muted-foreground">Candidats par étape et taux vers l&apos;étape suivante</p>
              </CardHeader>
              <CardContent>
                {!stageChartData.length ? (
                  <p className="text-sm text-muted-foreground py-8 text-center">Aucune donnée</p>
                ) : (
                  <ResponsiveContainer width="100%" height={Math.min(520, 120 + stageChartData.length * 48)}>
                    <BarChart data={stageChartData} margin={{ top: 8, right: 16, left: 8, bottom: 80 }}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-35} textAnchor="end" height={90} />
                      <YAxis allowDecimals={false} className="text-xs" />
                      <RechartsTooltip
                        content={({ active, payload }) => {
                          if (!active || !payload?.length) return null;
                          const p = payload[0].payload as {
                            fullName?: string;
                            candidats?: number;
                            conversion?: number;
                          };
                          return (
                            <div className="rounded-md border bg-background px-2 py-1.5 text-xs shadow-md">
                              <p className="font-medium mb-1">{p.fullName}</p>
                              <p className="text-muted-foreground">Candidats : {p.candidats}</p>
                              <p className="text-muted-foreground">
                                Conversion vers l&apos;étape suivante : {p.conversion ?? 0}%
                              </p>
                            </div>
                          );
                        }}
                      />
                      <Legend />
                      <Bar dataKey="candidats" name="Candidats" fill="#3b82f6" radius={[4, 4, 0, 0]}>
                        <LabelList
                          dataKey="conversion"
                          position="top"
                          formatter={(v: number) => (v > 0 ? `${v}%` : "")}
                          className="fill-muted-foreground text-[10px]"
                        />
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
                {stageChartData.length > 0 && d?.stage_conversion?.length ? (
                  <ul className="mt-4 space-y-1 text-xs text-muted-foreground border-t pt-3">
                    {d.stage_conversion.map((s) => (
                      <li key={`${s.stage_name}-${s.stage_position}`} className="flex justify-between gap-2">
                        <span className="truncate" title={s.stage_name}>{s.stage_name}</span>
                        <span className="tabular-nums shrink-0">
                          {s.conversion_rate.toFixed(1)}% vers suivante · ~{s.avg_days_in_stage.toFixed(1)} j dans l&apos;étape
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Time-to-hire par poste</CardTitle>
              <p className="text-sm text-muted-foreground">Délai moyen entre candidature et embauche</p>
            </CardHeader>
            <CardContent>
              {!d?.time_to_hire_by_job?.length ? (
                <p className="text-sm text-muted-foreground py-8 text-center">Aucune embauche sur la période sélectionnée</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Poste</TableHead>
                      <TableHead className="text-right">Embauches</TableHead>
                      <TableHead className="text-right">Moy. jours</TableHead>
                      <TableHead className="text-right">Min</TableHead>
                      <TableHead className="text-right">Max</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {d.time_to_hire_by_job.map((row) => (
                      <TableRow key={row.job_id}>
                        <TableCell className="font-medium">{row.job_title || "—"}</TableCell>
                        <TableCell className="text-right tabular-nums">{row.nb_hired}</TableCell>
                        <TableCell className="text-right tabular-nums">{row.avg_days.toFixed(1)}</TableCell>
                        <TableCell className="text-right tabular-nums">{row.min_days.toFixed(1)}</TableCell>
                        <TableCell className="text-right tabular-nums">{row.max_days.toFixed(1)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

// ─── Kanban Card ────────────────────────────────────────────────────

function CandidateCard({ candidate, onClick }: { candidate: Candidate; onClick: () => void }) {
  const ai = candidate.ai_score;
  const pal = ai != null ? recruitmentAiPalette(ai) : null;
  return (
    <div
      onClick={onClick}
      className={cn(
        "relative bg-white border rounded-lg p-3 cursor-pointer hover:shadow-md transition-shadow group",
        ai != null && "pb-7",
      )}
    >
      <div className="flex items-start gap-2">
        <Avatar className="h-8 w-8 flex-shrink-0 mt-0.5">
          <AvatarFallback className="text-xs bg-primary/10 text-primary font-medium">
            {candidate.first_name[0]}{candidate.last_name[0]}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium truncate group-hover:text-primary transition-colors">
            {candidate.first_name} {candidate.last_name}
          </p>
          {candidate.email && (
            <p className="text-xs text-muted-foreground truncate">{candidate.email}</p>
          )}
          {candidate.source && (
            <Badge variant="outline" className="mt-1 text-[10px] h-5">{candidate.source}</Badge>
          )}
        </div>
      </div>
      {ai != null && pal ? (
        <span
          className={cn(
            "pointer-events-none absolute bottom-1.5 right-1.5 rounded border px-1.5 py-0.5 text-[10px] font-bold tabular-nums",
            pal.badge,
          )}
          aria-label={`Score IA ${ai}`}
        >
          {ai}
        </span>
      ) : null}
    </div>
  );
}

// ─── Kanban Column ──────────────────────────────────────────────────

function KanbanColumn({
  stage,
  candidates,
  onCardClick,
  onCandidateDrop,
  isRh,
  onRename,
  onDelete,
  stageDragHandleProps,
}: {
  stage: PipelineStage;
  candidates: Candidate[];
  onCardClick: (c: Candidate) => void;
  onCandidateDrop: (candidateId: string, stageId: string) => void;
  isRh: boolean;
  onRename?: (name: string) => void;
  onDelete?: () => void;
  /** Poignée @dnd-kit (icône ⋮⋮ uniquement — évite le conflit avec le renommage) */
  stageDragHandleProps?: React.HTMLAttributes<HTMLButtonElement>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(stage.name);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dragCountRef = useRef(0);

  const bgColor = stage.stage_type === "rejected"
    ? "border-red-200 bg-red-50/50"
    : stage.stage_type === "hired"
      ? "border-green-200 bg-green-50/50"
      : "border-border bg-muted/30";

  const scrollViewportTint =
    stage.stage_type === "rejected"
      ? "[&_[data-radix-scroll-area-viewport]]:bg-red-50/50"
      : stage.stage_type === "hired"
        ? "[&_[data-radix-scroll-area-viewport]]:bg-green-50/50"
        : "[&_[data-radix-scroll-area-viewport]]:bg-muted/30";

  const startEditing = () => {
    setDraft(stage.name);
    setEditing(true);
    setTimeout(() => inputRef.current?.select(), 0);
  };

  const commitRename = () => {
    setEditing(false);
    const v = draft.trim();
    if (v && v !== stage.name && onRename) onRename(v);
  };

  const canDelete = isRh && stage.stage_type === "standard" && candidates.length === 0;

  return (
    <div
      className={`flex flex-col min-w-[260px] max-w-[300px] overflow-hidden rounded-lg border transition-colors duration-150 ${dragOver ? "ring-2 ring-primary/40 border-primary/40" : ""} ${bgColor}`}
      onDragOver={isRh ? (e) => {
        if (e.dataTransfer.types.includes("candidateid")) {
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
        }
      } : undefined}
      onDragEnter={isRh ? (e) => {
        if (e.dataTransfer.types.includes("candidateid")) {
          dragCountRef.current++;
          setDragOver(true);
        }
      } : undefined}
      onDragLeave={isRh ? () => {
        dragCountRef.current--;
        if (dragCountRef.current <= 0) { dragCountRef.current = 0; setDragOver(false); }
      } : undefined}
      onDrop={isRh ? (e) => {
        dragCountRef.current = 0;
        setDragOver(false);
        const candidateId = e.dataTransfer.getData("candidateId");
        if (candidateId) { e.preventDefault(); onCandidateDrop(candidateId, stage.id); }
      } : undefined}
    >
      {/* Header — réordonnancement via la poignée ⋮⋮ (@dnd-kit) */}
      <div className="px-3 py-2 border-b flex items-center gap-1.5">
        {isRh && stageDragHandleProps && (
          <button
            type="button"
            className="-ml-1 p-1 rounded-md shrink-0 cursor-grab active:cursor-grabbing touch-none text-muted-foreground hover:bg-muted/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            aria-label="Déplacer l&apos;étape"
            {...stageDragHandleProps}
          >
            <GripVertical className="h-4 w-4 opacity-70" />
          </button>
        )}

        {editing ? (
          <Input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commitRename}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitRename();
              if (e.key === "Escape") { setEditing(false); setDraft(stage.name); }
            }}
            className="h-7 text-sm font-semibold px-1.5 flex-1 min-w-0"
            autoFocus
          />
        ) : (
          <span
            className={`text-sm font-semibold truncate flex-1 min-w-0 ${isRh && onRename ? "cursor-pointer hover:underline decoration-dotted underline-offset-4" : ""}`}
            onClick={isRh && onRename ? (e) => { e.stopPropagation(); startEditing(); } : undefined}
            title={isRh && onRename ? "Cliquer pour renommer" : undefined}
          >
            {stage.name}
          </span>
        )}

        <Badge variant="secondary" className="h-5 text-[10px] px-1.5 shrink-0">
          {candidates.length}
        </Badge>

        {isRh && stage.stage_type === "standard" && (
          <button
            onClick={(e) => { e.stopPropagation(); if (canDelete && onDelete) onDelete(); }}
            disabled={!canDelete}
            className="p-0.5 rounded hover:bg-destructive/10 disabled:opacity-20 disabled:pointer-events-none text-muted-foreground hover:text-destructive transition-colors"
            title={canDelete ? "Supprimer cette étape" : candidates.length > 0 ? "Déplacez d'abord les candidats" : "Supprimer"}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      <ScrollArea
        className={cn(
          "flex-1 p-2 max-h-[calc(100vh-320px)]",
          scrollViewportTint,
          "[&_[data-radix-scroll-area-viewport]]:rounded-b-lg",
        )}
      >
        <div className="space-y-2">
          {candidates.map((c) => (
            <div
              key={c.id}
              draggable={isRh}
              onDragStart={isRh ? (e) => {
                e.dataTransfer.setData("candidateId", c.id);
                e.stopPropagation();
              } : undefined}
            >
              <CandidateCard candidate={c} onClick={() => onCardClick(c)} />
            </div>
          ))}
          {candidates.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-6">Aucun candidat</p>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

/** Vignettes récapitulatives : toutes les étapes visibles d’un coup ; clic pour centrer la colonne dans le défilement horizontal. */
function PipelineStageSummaryRow({
  stages,
  candidatesByStage,
}: {
  stages: PipelineStage[];
  candidatesByStage: Record<string, Candidate[]>;
}) {
  const scrollToStage = (stageId: string) => {
    document.getElementById(`recruitment-pipeline-stage-${stageId}`)?.scrollIntoView({
      behavior: "smooth",
      inline: "center",
      block: "nearest",
    });
  };

  return (
    <div
      className="flex flex-wrap gap-2 pb-1"
      role="navigation"
      aria-label="Résumé des étapes du pipeline"
    >
      {stages.map((stage) => {
        const count = candidatesByStage[stage.id]?.length ?? 0;
        const isRejected = stage.stage_type === "rejected";
        const isHired = stage.stage_type === "hired";
        return (
          <button
            key={stage.id}
            type="button"
            onClick={() => scrollToStage(stage.id)}
            className={cn(
              "inline-flex min-w-0 max-w-[min(100%,14rem)] items-center gap-2 rounded-lg border px-2.5 py-1.5 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              !isRejected && !isHired && "border-border bg-muted/30 hover:bg-muted/50",
              isRejected && "border-red-200 bg-red-50/50 hover:bg-red-50/70",
              isHired && "border-green-200 bg-green-50/50 hover:bg-green-50/70",
            )}
          >
            <span className="truncate font-medium" title={stage.name}>
              {stage.name}
            </span>
            <Badge variant="secondary" className="h-5 shrink-0 px-1.5 text-[10px] tabular-nums">
              {count}
            </Badge>
          </button>
        );
      })}
    </div>
  );
}

/** Colonne pipeline triable (comportement proche du Dock macOS : les autres colonnes cèdent la place). */
function SortableStageColumn({
  stage,
  candidates,
  onCardClick,
  onCandidateDrop,
  isRh,
  onRename,
  onDelete,
}: {
  stage: PipelineStage;
  candidates: Candidate[];
  onCardClick: (c: Candidate) => void;
  onCandidateDrop: (candidateId: string, stageId: string) => void;
  isRh: boolean;
  onRename?: (name: string) => void;
  onDelete?: () => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: stage.id });

  const style: CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 20 : undefined,
  };

  return (
    <div
      id={`recruitment-pipeline-stage-${stage.id}`}
      ref={setNodeRef}
      style={style}
      className={cn("shrink-0", isDragging && "opacity-95")}
    >
      <KanbanColumn
        stage={stage}
        candidates={candidates}
        onCardClick={onCardClick}
        onCandidateDrop={onCandidateDrop}
        isRh={isRh}
        onRename={onRename}
        onDelete={onDelete}
        stageDragHandleProps={{ ...listeners, ...attributes }}
      />
    </div>
  );
}

// ─── Add-stage column ───────────────────────────────────────────────

function AddStageColumn({ onAdd }: { onAdd: (name: string) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const submit = () => {
    const v = name.trim();
    if (!v) return;
    onAdd(v);
    setName("");
    setOpen(false);
  };

  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o) setTimeout(() => inputRef.current?.focus(), 0);
      }}
    >
      <PopoverTrigger asChild>
        <button
          className="flex flex-col items-center justify-center min-w-[48px] max-w-[48px] rounded-lg border-2 border-dashed border-muted-foreground/25 hover:border-primary/50 hover:bg-primary/5 transition-colors cursor-pointer min-h-[120px]"
          title="Ajouter une étape"
        >
          <Plus className="h-5 w-5 text-muted-foreground" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 p-3">
        <p className="text-sm font-medium mb-2">Nouvelle étape</p>
        <div className="flex gap-2">
          <Input
            ref={inputRef}
            placeholder="Ex: Test technique"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
            className="flex-1 h-8 text-sm"
          />
          <Button size="sm" className="h-8 px-3" disabled={!name.trim()} onClick={submit}>
            <Check className="h-4 w-4" />
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

// ─── Note audio (MediaRecorder) ─────────────────────────────────────

type NoteRecorderUiState = "idle" | "recording" | "recorded" | "uploading";

const NOTE_AUDIO_MAX_SECONDS = 300;

function formatNoteRecSecs(total: number): string {
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function CandidateNoteAudioRecorder({
  candidateId,
  companyId,
  audioUrl,
  onAudioUrl,
  disabled,
}: {
  candidateId: string;
  companyId: string;
  audioUrl: string | null;
  onAudioUrl: (url: string | null) => void;
  disabled?: boolean;
}) {
  const { toast } = useToast();
  const [ui, setUi] = useState<NoteRecorderUiState>("idle");
  const [seconds, setSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const previewUrlRef = useRef<string | null>(null);
  const recordedBlobRef = useRef<Blob | null>(null);
  const elapsedRef = useRef(0);

  const stopTimer = () => {
    if (timerRef.current != null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const cleanupStream = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  };

  const revokePreview = () => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
  };

  useEffect(
    () => () => {
      stopTimer();
      cleanupStream();
      revokePreview();
      mediaRecorderRef.current = null;
    },
    [],
  );

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      let mime = "audio/webm";
      if (typeof MediaRecorder !== "undefined" && !MediaRecorder.isTypeSupported("audio/webm")) {
        if (MediaRecorder.isTypeSupported("audio/ogg;codecs=opus")) {
          mime = "audio/ogg;codecs=opus";
        } else {
          mime = "";
        }
      }
      const options: MediaRecorderOptions | undefined = mime ? { mimeType: mime } : undefined;
      const mr = new MediaRecorder(stream, options);
      chunksRef.current = [];
      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mr.onstop = () => {
        stopTimer();
        cleanupStream();
        const blobType = mr.mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: blobType });
        recordedBlobRef.current = blob;
        revokePreview();
        const url = URL.createObjectURL(blob);
        previewUrlRef.current = url;
        setUi("recorded");
      };
      mediaRecorderRef.current = mr;
      elapsedRef.current = 0;
      setSeconds(0);
      setUi("recording");
      mr.start(1000);
      timerRef.current = setInterval(() => {
        elapsedRef.current += 1;
        setSeconds(elapsedRef.current);
        if (elapsedRef.current >= NOTE_AUDIO_MAX_SECONDS) {
          mr.stop();
        }
      }, 1000);
    } catch {
      toast({
        title: "Permission micro refusée",
        description: "Autorisez l'accès au microphone pour enregistrer une note audio.",
        variant: "destructive",
      });
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
  };

  const discardRecording = () => {
    revokePreview();
    recordedBlobRef.current = null;
    elapsedRef.current = 0;
    setSeconds(0);
    setUi("idle");
  };

  const confirmUpload = async () => {
    const blob = recordedBlobRef.current;
    if (!blob) return;
    setUi("uploading");
    try {
      const { audio_url } = await uploadNoteAudio(candidateId, companyId, blob);
      onAudioUrl(audio_url);
      revokePreview();
      recordedBlobRef.current = null;
      elapsedRef.current = 0;
      setSeconds(0);
      setUi("idle");
    } catch {
      toast({
        title: "Erreur",
        description: "Impossible d'envoyer l'enregistrement.",
        variant: "destructive",
      });
      setUi("recorded");
    }
  };

  if (audioUrl) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <Badge className="bg-emerald-600 gap-1 font-normal">
          Audio joint
        </Badge>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="h-7 w-7 shrink-0"
          aria-label="Retirer l'audio"
          disabled={disabled}
          onClick={() => onAudioUrl(null)}
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>
    );
  }

  if (ui === "uploading") {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Envoi de l&apos;audio…
      </div>
    );
  }

  if (ui === "recording") {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <span className="flex items-center gap-1.5 text-xs font-medium text-red-600">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-red-600" />
          </span>
          Enregistrement
        </span>
        <span className="text-sm tabular-nums text-muted-foreground">{formatNoteRecSecs(seconds)}</span>
        <Button
          type="button"
          size="sm"
          variant="destructive"
          className="h-8 gap-1"
          onClick={stopRecording}
        >
          <Square className="h-3.5 w-3.5 fill-current" />
          Stop
        </Button>
      </div>
    );
  }

  if (ui === "recorded" && previewUrlRef.current) {
    return (
      <div className="space-y-2 rounded-md border bg-background/80 p-2">
        <audio src={previewUrlRef.current} controls className="h-8 w-full max-w-md" />
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="outline" className="h-8 gap-1" onClick={discardRecording}>
            <Trash2 className="h-3.5 w-3.5" />
            Supprimer
          </Button>
          <Button type="button" size="sm" className="h-8" onClick={confirmUpload} disabled={disabled}>
            Utiliser cet enregistrement
          </Button>
        </div>
      </div>
    );
  }

  return (
    <Button
      type="button"
      size="sm"
      variant="outline"
      className="h-8 gap-1"
      disabled={disabled}
      onClick={startRecording}
    >
      <Mic className="h-3.5 w-3.5" />
      Enregistrer un audio
    </Button>
  );
}

// ─── Candidate Slide-over ───────────────────────────────────────────

function CandidateSlideOver({
  candidate,
  open,
  onClose,
  isRh,
  stages,
  onMove,
  onHire,
  onRequestReject,
  onScheduleInterview,
  companyId,
  onCandidateRefresh,
}: {
  candidate: Candidate | null;
  open: boolean;
  onClose: () => void;
  isRh: boolean;
  stages: PipelineStage[];
  onMove: (candidateId: string, stageId: string) => void;
  onHire: (candidateId: string) => void;
  onRequestReject: (candidateId: string) => void;
  onScheduleInterview: () => void;
  companyId: string;
  onCandidateRefresh: (c: Candidate) => void;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const cvFileInputRef = useRef<HTMLInputElement>(null);
  const [noteText, setNoteText] = useState("");
  const [noteAudioUrl, setNoteAudioUrl] = useState<string | null>(null);
  const [opinionRating, setOpinionRating] = useState<"favorable" | "defavorable" | null>(null);
  const [opinionComment, setOpinionComment] = useState("");
  const [interviewEditingId, setInterviewEditingId] = useState<string | null>(null);
  const [interviewSummaryDraft, setInterviewSummaryDraft] = useState("");
  const candidateId = candidate?.id;

  const { data: notes = [], isLoading: loadingNotes } = useQuery({
    queryKey: ["recruitment", "notes", candidateId],
    queryFn: () => getNotes(candidateId!),
    enabled: !!candidateId,
  });

  const { data: opinions = [], isLoading: loadingOpinions } = useQuery({
    queryKey: ["recruitment", "opinions", candidateId],
    queryFn: () => getOpinions(candidateId!),
    enabled: !!candidateId,
  });

  const { data: interviews = [], isLoading: loadingInterviews } = useQuery({
    queryKey: ["recruitment", "interviews", candidateId],
    queryFn: () => getInterviews(candidateId!),
    enabled: !!candidateId,
  });

  const { data: timeline = [], isLoading: loadingTimeline } = useQuery({
    queryKey: ["recruitment", "timeline", candidateId],
    queryFn: () => getTimeline(candidateId!),
    enabled: !!candidateId,
  });

  useEffect(() => {
    setNoteAudioUrl(null);
  }, [candidateId]);

  const addNoteMutation = useMutation({
    mutationFn: (payload: { content: string; audio_url?: string | null }) =>
      createNote({
        candidate_id: candidateId!,
        content: payload.content,
        ...(payload.audio_url ? { audio_url: payload.audio_url } : {}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recruitment", "notes", candidateId] });
      queryClient.invalidateQueries({ queryKey: ["recruitment", "timeline", candidateId] });
      setNoteText("");
      setNoteAudioUrl(null);
      toast({ title: "Note ajoutée" });
    },
  });

  const addOpinionMutation = useMutation({
    mutationFn: (data: { rating: "favorable" | "defavorable"; comment?: string }) =>
      createOpinion({ candidate_id: candidateId!, ...data }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recruitment", "opinions", candidateId] });
      queryClient.invalidateQueries({ queryKey: ["recruitment", "timeline", candidateId] });
      setOpinionRating(null);
      setOpinionComment("");
      toast({ title: "Avis enregistré" });
    },
  });

  const uploadCvMutation = useMutation({
    mutationFn: (file: File) => uploadCandidateCV(candidateId!, companyId, file),
    onSuccess: (data) => {
      if (candidate) {
        onCandidateRefresh({ ...candidate, cv_url: data.cv_url });
      }
      queryClient.invalidateQueries({ queryKey: ["recruitment", "candidates"] });
      toast({ title: "CV téléversé" });
      if (cvFileInputRef.current) cvFileInputRef.current.value = "";
    },
    onError: () => {
      toast({ title: "Erreur", description: "Impossible de téléverser le CV.", variant: "destructive" });
    },
  });

  const updateInterviewSummaryMutation = useMutation({
    mutationFn: ({ interviewId, summary }: { interviewId: string; summary: string }) =>
      updateInterview(interviewId, { summary }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recruitment", "interviews", candidateId] });
      queryClient.invalidateQueries({ queryKey: ["recruitment", "timeline", candidateId] });
      setInterviewEditingId(null);
      setInterviewSummaryDraft("");
      toast({ title: "Compte-rendu enregistré" });
    },
    onError: () => {
      toast({
        title: "Erreur",
        description: "Impossible d'enregistrer le compte-rendu.",
        variant: "destructive",
      });
    },
  });

  const { data: scoringDetail, isLoading: scoringDetailLoading } = useQuery({
    queryKey: ["recruitment", "score", candidateId, companyId],
    queryFn: () => getCandidateScore(candidateId!, companyId),
    enabled: Boolean(
      open && candidateId && companyId && isRh && candidate?.ai_score != null,
    ),
  });

  const scoreAiMutation = useMutation({
    mutationFn: () => scoreCandidateAI(candidateId!, companyId),
    onSuccess: (data: ScoringResult) => {
      if (candidate) {
        onCandidateRefresh({
          ...candidate,
          ai_score: data.score,
          ai_scored_at: data.scored_at,
        });
      }
      queryClient.setQueryData(["recruitment", "score", candidateId, companyId], data);
      queryClient.invalidateQueries({ queryKey: ["recruitment", "candidates"] });
      toast({ title: "Analyse IA terminée" });
    },
    onError: (err: unknown) => {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 503) {
        toast({
          title: "Clé API IA non configurée",
          description: "Configurez OPENAI_API_KEY sur le backend.",
          variant: "destructive",
        });
        return;
      }
      toast({
        title: "Erreur",
        description: "Impossible de lancer l'analyse IA.",
        variant: "destructive",
      });
    },
  });

  if (!candidate) return null;

  const currentStage = stages.find((s) => s.id === candidate.current_stage_id);
  const favorableCount = opinions.filter((o) => o.rating === "favorable").length;
  const defavorableCount = opinions.filter((o) => o.rating === "defavorable").length;

  const showRhActions =
    isRh && currentStage?.stage_type !== "rejected" && currentStage?.stage_type !== "hired";
  const favorableLabel = `${favorableCount} favorable${favorableCount !== 1 ? "s" : ""}`;
  const defavorableLabel = `${defavorableCount} défavorable${defavorableCount !== 1 ? "s" : ""}`;
  const entryDateLabel = candidate.hired_at
    ? `Entrée le ${new Date(candidate.hired_at).toLocaleDateString("fr-FR")}`
    : `Ajouté le ${new Date(candidate.created_at).toLocaleDateString("fr-FR")}`;
  const standardStages = [...stages]
    .filter((s) => s.stage_type === "standard")
    .sort((a, b) => a.position - b.position);
  const currentStandardIndex = standardStages.findIndex((s) => s.id === candidate.current_stage_id);
  const nextStandardStage =
    currentStandardIndex >= 0 ? standardStages[currentStandardIndex + 1] : null;

  const scoringScoreDisplayed =
    scoringDetail?.score ?? (candidate.ai_score != null ? candidate.ai_score : null);
  const scoringPal =
    scoringScoreDisplayed != null ? recruitmentAiPalette(scoringScoreDisplayed) : null;

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent className="w-full sm:max-w-xl p-0 flex flex-col h-full max-h-[100dvh]">
        {/* Bloc A — Identité + contact rapide (à droite de l’avatar) */}
        <div className="flex-shrink-0 z-10 bg-background border-b px-6 pt-4 pb-4 pr-14">
          <div className="flex gap-3 items-start min-w-0">
            <Avatar className="h-11 w-11 shrink-0">
              <AvatarFallback className="bg-primary/10 text-primary font-semibold text-sm">
                {candidate.first_name[0]}{candidate.last_name[0]}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <SheetTitle className="text-left text-lg font-semibold leading-tight">
                {candidate.first_name} {candidate.last_name}
              </SheetTitle>
              {currentStage && (
                <Badge
                  variant={currentStage.stage_type === "rejected" ? "destructive" : currentStage.stage_type === "hired" ? "default" : "secondary"}
                  className="mt-2"
                >
                  {currentStage.name}
                </Badge>
              )}
            </div>
            <div className="shrink-0 text-right text-xs space-y-1.5 max-w-[min(50%,11rem)] sm:max-w-[13rem] pt-0.5 border-l border-border/60 pl-3 ml-1">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Contact</p>
              {candidate.email ? (
                <a href={`mailto:${candidate.email}`} className="flex items-start justify-end gap-1.5 text-primary hover:underline break-all">
                  <Mail className="h-3 w-3 shrink-0 mt-0.5 text-muted-foreground" />
                  <span>{candidate.email}</span>
                </a>
              ) : (
                <p className="flex items-center justify-end gap-1.5 text-muted-foreground">
                  <Mail className="h-3 w-3 shrink-0" />
                  <span>—</span>
                </p>
              )}
              {candidate.phone ? (
                <a href={`tel:${candidate.phone.replace(/\s/g, "")}`} className="flex items-center justify-end gap-1.5 hover:text-primary">
                  <Phone className="h-3 w-3 shrink-0 text-muted-foreground" />
                  <span>{candidate.phone}</span>
                </a>
              ) : (
                <p className="flex items-center justify-end gap-1.5 text-muted-foreground">
                  <Phone className="h-3 w-3 shrink-0" />
                  <span>—</span>
                </p>
              )}
              <p className="flex items-start justify-end gap-1.5 text-muted-foreground">
                <Calendar className="h-3 w-3 shrink-0 mt-0.5" />
                <span className="leading-snug">{entryDateLabel}</span>
              </p>
            </div>
          </div>
        </div>

        {/* Bloc B — Cockpit RH + avis (fixe sous l’identité) */}
        <div className="flex-shrink-0 border-b bg-muted/30 px-6 py-4 space-y-4">
          {showRhActions && (
            <div className="flex flex-wrap gap-2 items-center" aria-label="Actions sur le candidat">
              <Button
                size="sm"
                className="h-9 text-xs shrink-0"
                variant="outline"
                disabled={!nextStandardStage}
                onClick={() => {
                  if (!nextStandardStage) return;
                  onMove(candidate.id, nextStandardStage.id);
                }}
              >
                Passer à l&apos;étape suivante
              </Button>
              <Button
                size="sm"
                className="h-9 text-xs font-medium bg-green-600 hover:bg-green-700 text-white shrink-0"
                onClick={() => onHire(candidate.id)}
              >
                Offre d&apos;emploi
              </Button>
              <Button
                size="sm"
                variant="destructive"
                className="h-9 text-xs shrink-0"
                onClick={() => onRequestReject(candidate.id)}
              >
                Refuser
              </Button>
            </div>
          )}

          <div className="space-y-3" aria-labelledby="candidate-section-avis">
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <h3 id="candidate-section-avis" className="text-sm font-semibold">
                Avis
              </h3>
              <span className="text-sm text-muted-foreground">
                {favorableLabel} / {defavorableLabel}
              </span>
            </div>
            {loadingOpinions ? (
              <Skeleton className="h-16 w-full" />
            ) : (
              <>
                {opinions.length > 0 && (
                  <div className="space-y-2 max-h-28 overflow-y-auto pr-1">
                    {opinions.map((o) => (
                      <div key={o.id} className="flex items-start gap-2">
                        <Badge variant={o.rating === "favorable" ? "default" : "destructive"} className="text-[10px] shrink-0 mt-0.5">
                          {o.rating === "favorable" ? "+" : "−"}
                        </Badge>
                        <div className="text-xs leading-snug min-w-0">
                          <span className="font-medium">{o.author_first_name} {o.author_last_name}</span>
                          {o.comment && <span className="text-muted-foreground"> — {o.comment}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <div className="space-y-2 p-3 bg-background/80 border rounded-lg">
                  <p className="text-xs font-medium text-muted-foreground">Donner un avis</p>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant={opinionRating === "favorable" ? "default" : "outline"}
                      className="h-8 text-xs"
                      onClick={() => setOpinionRating("favorable")}
                    >
                      <ThumbsUp className="h-3.5 w-3.5 mr-1.5" /> Favorable
                    </Button>
                    <Button
                      size="sm"
                      variant={opinionRating === "defavorable" ? "destructive" : "outline"}
                      className="h-8 text-xs"
                      onClick={() => setOpinionRating("defavorable")}
                    >
                      <ThumbsDown className="h-3.5 w-3.5 mr-1.5" /> Défavorable
                    </Button>
                  </div>
                  {opinionRating && (
                    <div className="flex flex-col gap-2 pt-1">
                      <Input
                        placeholder="Commentaire (optionnel)"
                        className="h-8 text-xs"
                        value={opinionComment}
                        onChange={(e) => setOpinionComment(e.target.value)}
                      />
                      <Button
                        size="sm"
                        className="h-8 text-xs w-fit"
                        disabled={addOpinionMutation.isPending}
                        onClick={() => addOpinionMutation.mutate({ rating: opinionRating, comment: opinionComment || undefined })}
                      >
                        {addOpinionMutation.isPending && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}
                        Valider l&apos;avis
                      </Button>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>

        {(isRh && companyId) || candidate.ai_score != null ? (
          <div
            className="flex-shrink-0 border-b bg-muted/20 px-6 py-4 space-y-3"
            aria-labelledby="candidate-section-ai-score"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 id="candidate-section-ai-score" className="text-sm font-semibold">
                Scoring IA
              </h3>
              {isRh && companyId ? (
                candidate.ai_score != null ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8 text-xs"
                    disabled={scoreAiMutation.isPending}
                    onClick={() => scoreAiMutation.mutate()}
                  >
                    {scoreAiMutation.isPending ? (
                      <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                    ) : (
                      <RefreshCw className="h-3.5 w-3.5 mr-1" />
                    )}
                    Recalculer
                  </Button>
                ) : (
                  <Button
                    type="button"
                    size="sm"
                    className="h-8 text-xs"
                    disabled={scoreAiMutation.isPending}
                    onClick={() => scoreAiMutation.mutate()}
                  >
                    {scoreAiMutation.isPending ? (
                      <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                    ) : (
                      <Sparkles className="h-3.5 w-3.5 mr-1" />
                    )}
                    Analyser avec l&apos;IA
                  </Button>
                )
              ) : null}
            </div>
            {candidate.ai_score != null && scoringPal ? (
              <div className="flex flex-wrap items-center gap-2">
                <Badge className={cn("text-[11px] font-semibold border", scoringPal.badge)}>
                  {(scoringDetail?.mention ?? "—")} · {candidate.ai_score}/100
                </Badge>
              </div>
            ) : null}
            {!isRh && candidate.ai_score != null && !scoringDetail ? (
              <p className="text-xs text-muted-foreground">
                Détail du scoring disponible pour les utilisateurs RH.
              </p>
            ) : null}
            {isRh && companyId && candidate.ai_score != null && scoringDetailLoading ? (
              <Skeleton className="h-28 w-full rounded-lg" />
            ) : null}
            {isRh && companyId && scoringDetail && scoringPal ? (
              <div className="space-y-4 rounded-lg border bg-background/90 p-4 shadow-sm">
                <div className="flex flex-wrap items-center gap-4">
                  <div
                    className={cn(
                      "flex h-16 w-16 shrink-0 items-center justify-center rounded-full border-4 bg-muted/40 text-lg font-bold tabular-nums",
                      scoringScoreDisplayed != null &&
                        scoringScoreDisplayed >= 80 &&
                        "border-emerald-600 text-emerald-900",
                      scoringScoreDisplayed != null &&
                        scoringScoreDisplayed >= 60 &&
                        scoringScoreDisplayed < 80 &&
                        "border-blue-600 text-blue-900",
                      scoringScoreDisplayed != null &&
                        scoringScoreDisplayed >= 40 &&
                        scoringScoreDisplayed < 60 &&
                        "border-orange-500 text-orange-900",
                      scoringScoreDisplayed != null &&
                        scoringScoreDisplayed < 40 &&
                        "border-red-600 text-red-900",
                    )}
                  >
                    {scoringDetail.score}
                  </div>
                  <div className="min-w-0 flex-1 space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">Adéquation</p>
                    <div className="h-2 w-full max-w-xs overflow-hidden rounded-full bg-muted">
                      <div
                        className={cn("h-full rounded-full transition-all", scoringPal.bar)}
                        style={{ width: `${Math.min(100, Math.max(0, scoringDetail.score))}%` }}
                      />
                    </div>
                    <Badge className={cn("mt-1 text-[10px] font-semibold border", scoringPal.badge)}>
                      {scoringDetail.mention}
                    </Badge>
                  </div>
                </div>
                <div>
                  <p className="text-xs font-semibold text-emerald-800 mb-2 flex items-center gap-1">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Points forts
                  </p>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    {(scoringDetail.points_forts ?? []).map((p, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-emerald-600 shrink-0">✓</span>
                        <span>{p}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-xs font-semibold text-orange-800 mb-2 flex items-center gap-1">
                    <AlertCircle className="h-3.5 w-3.5" /> Points faibles
                  </p>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    {(scoringDetail.points_faibles ?? []).map((p, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-orange-600 shrink-0">!</span>
                        <span>{p}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-xs font-semibold text-muted-foreground mb-1">Recommandation</p>
                  <p className="text-sm italic text-foreground/90">{scoringDetail.recommandation}</p>
                </div>
                <p className="text-[10px] text-muted-foreground">
                  Analyse du{" "}
                  {new Date(scoringDetail.scored_at).toLocaleString("fr-FR", {
                    dateStyle: "short",
                    timeStyle: "short",
                  })}
                </p>
              </div>
            ) : null}
          </div>
        ) : null}

        {/* Bloc C — Consultation (scroll) : dossier → notes → entretiens → activité */}
        <ScrollArea className="flex-1 min-h-0">
          <div className="px-6 py-4 space-y-8 pb-10">
            <section aria-labelledby="candidate-section-dossier" className="space-y-5">
              <h3 id="candidate-section-dossier" className="text-sm font-semibold">
                Dossier candidats
              </h3>
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">CV</h4>
                <input
                  ref={cvFileInputRef}
                  type="file"
                  className="sr-only"
                  accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f && candidateId && companyId) uploadCvMutation.mutate(f);
                  }}
                />
                {candidate.cv_url ? (
                  <div className="space-y-2">
                    <a
                      href={candidate.cv_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-3 rounded-lg border bg-muted/30 p-3 text-sm hover:bg-muted/50 transition-colors"
                    >
                      <FileText className="h-8 w-8 text-primary shrink-0" />
                      <span className="font-medium text-primary underline-offset-4 hover:underline">
                        Télécharger le CV
                      </span>
                    </a>
                    {isRh && companyId ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-8 text-xs"
                        disabled={uploadCvMutation.isPending}
                        onClick={() => cvFileInputRef.current?.click()}
                      >
                        {uploadCvMutation.isPending && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}
                        Remplacer le CV
                      </Button>
                    ) : null}
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed bg-muted/20 p-4 flex flex-col gap-3 sm:flex-row sm:items-start">
                    <FileText className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />
                    <div className="min-w-0 space-y-2 flex-1">
                      <p className="text-sm font-medium">Aucun CV joint</p>
                      <p className="text-xs text-muted-foreground">
                        Téléversez un fichier PDF ou Word pour l&apos;associer au dossier.
                      </p>
                      {isRh && companyId ? (
                        <Button
                          type="button"
                          size="sm"
                          className="h-8 text-xs w-fit"
                          disabled={uploadCvMutation.isPending}
                          onClick={() => cvFileInputRef.current?.click()}
                        >
                          {uploadCvMutation.isPending && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}
                          Uploader un CV
                        </Button>
                      ) : null}
                    </div>
                  </div>
                )}
              </div>
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                  Autres documents personnels
                </h4>
                <div className="rounded-lg border border-dashed bg-muted/20 p-4 flex gap-3 items-start">
                  <FileText className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />
                  <div className="min-w-0 space-y-1">
                    <p className="text-sm font-medium">Aucun document complémentaire</p>
                    <p className="text-xs text-muted-foreground">
                      Pièces d&apos;identité, diplômes, attestations ou autres justificatifs pourront être ajoutés ici lorsque le dépôt de fichiers sera disponible.
                    </p>
                  </div>
                </div>
              </div>
            </section>

            <Separator />

            <section aria-labelledby="candidate-section-notes">
              <h3 id="candidate-section-notes" className="text-sm font-semibold mb-3">
                Notes ({notes.length})
              </h3>
              <div className="space-y-4">
                <div className="space-y-2 p-3 bg-muted/50 rounded-lg border border-border/60">
                  <Textarea
                    placeholder="Ajouter une note…"
                    className="text-sm min-h-[72px]"
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                  />
                  {candidateId && companyId ? (
                    <CandidateNoteAudioRecorder
                      key={candidateId}
                      candidateId={candidateId}
                      companyId={companyId}
                      audioUrl={noteAudioUrl}
                      onAudioUrl={setNoteAudioUrl}
                      disabled={addNoteMutation.isPending}
                    />
                  ) : null}
                  <Button
                    size="sm"
                    className="h-9 text-xs"
                    disabled={(!noteText.trim() && !noteAudioUrl) || addNoteMutation.isPending}
                    onClick={() => {
                      const text = noteText.trim();
                      if (!text && !noteAudioUrl) return;
                      addNoteMutation.mutate({
                        content: text || "(Note vocale)",
                        audio_url: noteAudioUrl ?? undefined,
                      });
                    }}
                  >
                    {addNoteMutation.isPending && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}
                    Ajouter une note
                  </Button>
                </div>
                {loadingNotes ? (
                  <div className="space-y-2">{[1, 2].map((i) => <Skeleton key={i} className="h-16" />)}</div>
                ) : notes.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-4">Aucune note pour ce candidat.</p>
                ) : (
                  <div className="space-y-3">
                    {notes.map((n) => (
                      <div key={n.id} className="border rounded-lg p-3">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="text-xs font-medium">{n.author_first_name} {n.author_last_name}</span>
                          <span className="text-[10px] text-muted-foreground shrink-0">
                            {new Date(n.created_at).toLocaleDateString("fr-FR")} à {new Date(n.created_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
                          </span>
                        </div>
                        <p className="text-sm whitespace-pre-wrap">{n.content}</p>
                        {n.audio_url ? (
                          <audio src={n.audio_url} controls className="mt-2 h-8 w-full max-w-md" />
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>

            <Separator />

            <section aria-labelledby="candidate-section-interviews">
              <h3 id="candidate-section-interviews" className="text-sm font-semibold mb-3">
                Entretiens ({interviews.length})
              </h3>
              <div className="space-y-4">
                {isRh && (
                  <Button size="sm" className="h-9 text-xs w-full" onClick={onScheduleInterview}>
                    <Plus className="h-3.5 w-3.5 mr-1.5" /> Planifier un entretien
                  </Button>
                )}
                {loadingInterviews ? (
                  <div className="space-y-2">{[1, 2].map((i) => <Skeleton key={i} className="h-20" />)}</div>
                ) : interviews.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-4">Aucun entretien planifié.</p>
                ) : (
                  <div className="space-y-3">
                    {interviews.map((i) => (
                      <div key={i.id} className="border rounded-lg p-3">
                        <div className="flex items-center justify-between mb-1 gap-2">
                          <span className="text-sm font-medium">{i.interview_type}</span>
                          <Badge variant={i.status === "completed" ? "default" : i.status === "cancelled" ? "destructive" : "secondary"} className="text-[10px] shrink-0">
                            {i.status === "planned" ? "Planifié" : i.status === "completed" ? "Terminé" : "Annulé"}
                          </Badge>
                        </div>
                        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3 w-3 shrink-0" />
                            {new Date(i.scheduled_at).toLocaleDateString("fr-FR")}
                          </span>
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3 shrink-0" />
                            {new Date(i.scheduled_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })} · {i.duration_minutes} min
                          </span>
                          {i.location && (
                            <span className="flex items-center gap-1 min-w-0"><MapPin className="h-3 w-3 shrink-0" />{i.location}</span>
                          )}
                          {i.meeting_link && (
                            <a href={i.meeting_link} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-primary hover:underline">
                              <Link2 className="h-3 w-3 shrink-0" />Lien
                            </a>
                          )}
                        </div>
                        {i.participants && i.participants.length > 0 && (
                          <div className="flex gap-1 mt-2 flex-wrap">
                            {i.participants.map((p) => (
                              <Badge key={p.user_id} variant="outline" className="text-[10px] h-5">
                                {p.first_name} {p.last_name}
                              </Badge>
                            ))}
                          </div>
                        )}
                        <div className="mt-2 space-y-2">
                          {interviewEditingId === i.id ? (
                            <>
                              <Textarea
                                className="text-xs min-h-[88px]"
                                value={interviewSummaryDraft}
                                onChange={(e) => setInterviewSummaryDraft(e.target.value)}
                                placeholder="Compte-rendu d'entretien…"
                              />
                              <div className="flex flex-wrap gap-2">
                                <Button
                                  type="button"
                                  size="sm"
                                  className="h-8 text-xs"
                                  disabled={updateInterviewSummaryMutation.isPending}
                                  onClick={() =>
                                    updateInterviewSummaryMutation.mutate({
                                      interviewId: i.id,
                                      summary: interviewSummaryDraft,
                                    })
                                  }
                                >
                                  {updateInterviewSummaryMutation.isPending && (
                                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                                  )}
                                  Enregistrer
                                </Button>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  className="h-8 text-xs"
                                  disabled={updateInterviewSummaryMutation.isPending}
                                  onClick={() => {
                                    setInterviewEditingId(null);
                                    setInterviewSummaryDraft("");
                                  }}
                                >
                                  Annuler
                                </Button>
                              </div>
                            </>
                          ) : (
                            <>
                              {i.summary ? (
                                <div className="space-y-1">
                                  <p className="text-xs bg-muted/50 p-2 rounded whitespace-pre-wrap">{i.summary}</p>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    className="h-7 text-[10px]"
                                    onClick={() => {
                                      setInterviewEditingId(i.id);
                                      setInterviewSummaryDraft(i.summary || "");
                                    }}
                                  >
                                    Modifier
                                  </Button>
                                </div>
                              ) : (
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  className="h-8 text-xs"
                                  onClick={() => {
                                    setInterviewEditingId(i.id);
                                    setInterviewSummaryDraft("");
                                  }}
                                >
                                  Ajouter un compte-rendu
                                </Button>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>

            <Separator />

            <section aria-labelledby="candidate-section-timeline">
              <h3 id="candidate-section-timeline" className="text-sm font-semibold mb-3">
                Activité
              </h3>
              <div>
                {loadingTimeline ? (
                  <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}</div>
                ) : timeline.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-4">Aucun événement.</p>
                ) : (
                  <div className="relative pl-4 border-l-2 border-muted space-y-4 pb-2">
                    {timeline.map((e) => (
                      <div key={e.id} className="relative">
                        <div className="absolute -left-[21px] top-1 h-3 w-3 rounded-full border-2 border-background bg-primary" />
                        <div className="ml-2">
                          <p className="text-sm">{e.description}</p>
                          <p className="text-[10px] text-muted-foreground">
                            {e.actor_first_name && `${e.actor_first_name} ${e.actor_last_name} · `}
                            {new Date(e.created_at).toLocaleDateString("fr-FR")} à {new Date(e.created_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────

export default function Recruitment() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? "";
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [mainSection, setMainSection] = useState<"pipeline" | "analytics">("pipeline");
  const [viewMode, setViewMode] = useState<"kanban" | "list">("kanban");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [searchText, setSearchText] = useState("");
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(null);
  const [slideOverOpen, setSlideOverOpen] = useState(false);
  const [showCreateJob, setShowCreateJob] = useState(false);
  const [showCreateCandidate, setShowCreateCandidate] = useState(false);
  const [showHireModal, setShowHireModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [showInterviewModal, setShowInterviewModal] = useState(false);
  const [deleteStageTarget, setDeleteStageTarget] = useState<PipelineStage | null>(null);
  const [showDuplicateEmployeeModal, setShowDuplicateEmployeeModal] = useState(false);
  const [hireCandidateId, setHireCandidateId] = useState<string | null>(null);
  const [rejectCandidateId, setRejectCandidateId] = useState<string | null>(null);
  const [rejectStageId, setRejectStageId] = useState<string | null>(null);
  const [duplicateEmployeeInfo, setDuplicateEmployeeInfo] = useState<{
    id: string; first_name: string; last_name: string; email: string;
  } | null>(null);
  const [hireSuccessEmployeeId, setHireSuccessEmployeeId] = useState<string | null>(null);

  // Forms state
  const [newJob, setNewJob] = useState({ title: "", description: "", location: "", contract_type: "CDI", status: "active" });
  const [newCandidate, setNewCandidate] = useState({ first_name: "", last_name: "", email: "", phone: "", source: "" });
  const [hireData, setHireData] = useState({
    hire_date: "",
    job_title: "",
    contract_type: "CDI",
    site: "",
    service_id: "",
  });
  const [rejectReason, setRejectReason] = useState("");
  const [rejectDetail, setRejectDetail] = useState("");
  const [interviewData, setInterviewData] = useState({ interview_type: "Entretien RH", scheduled_at: "", duration_minutes: 60, location: "", meeting_link: "" });
  const [interviewParticipantIds, setInterviewParticipantIds] = useState<string[]>([]);

  const isRh = user?.role === "rh" || user?.role === "admin" || user?.role === "collaborateur_rh";

  const servicesQuery = useQuery({
    queryKey: ["recruitment-company-services", companyId],
    queryFn: () => listCompanyServices(),
    enabled: Boolean(companyId),
  });

  const { data: interviewCompanyUsers = [], isLoading: loadingInterviewCompanyUsers } = useQuery({
    queryKey: ["recruitment-interview-company-users", companyId],
    queryFn: async () => {
      const res = await apiClient.get<
        Array<{
          id: string;
          first_name?: string | null;
          last_name?: string | null;
          email?: string | null;
        }>
      >(`/api/users/company/${companyId}`, {
        headers: { "X-Active-Company": companyId },
      });
      const rows = res.data ?? [];
      return [...rows].sort((a, b) => {
        const na = `${a.first_name ?? ""} ${a.last_name ?? ""}`.trim().toLowerCase();
        const nb = `${b.first_name ?? ""} ${b.last_name ?? ""}`.trim().toLowerCase();
        return na.localeCompare(nb, "fr");
      });
    },
    enabled: Boolean(showInterviewModal && companyId && isRh),
  });

  useEffect(() => {
    if (!showInterviewModal) setInterviewParticipantIds([]);
  }, [showInterviewModal]);

  // Queries
  const { data: jobs = [], isLoading: loadingJobs } = useQuery({
    queryKey: ["recruitment", "jobs"],
    queryFn: () => getJobs(),
  });

  const activeJobs = jobs.filter((j) => j.status === "active");

  const effectiveJobId = selectedJobId || (activeJobs.length > 0 ? activeJobs[0].id : null);

  const { data: stages = [], isLoading: loadingStages } = useQuery({
    queryKey: ["recruitment", "stages", effectiveJobId],
    queryFn: () => getPipelineStages(effectiveJobId!),
    enabled: !!effectiveJobId,
  });

  const { data: candidates = [], isLoading: loadingCandidates } = useQuery({
    queryKey: ["recruitment", "candidates", effectiveJobId, searchText],
    queryFn: () => getCandidates({ job_id: effectiveJobId || undefined, search: searchText || undefined }),
    enabled: !!effectiveJobId,
  });

  const { data: rejectionReasons } = useQuery({
    queryKey: ["recruitment", "rejection-reasons"],
    queryFn: getRejectionReasons,
  });

  // Mutations
  const createJobMutation = useMutation({
    mutationFn: () => createJob(newJob),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: ["recruitment", "jobs"] });
      setShowCreateJob(false);
      setNewJob({ title: "", description: "", location: "", contract_type: "CDI", status: "active" });
      setSelectedJobId(job.id);
      toast({ title: "Poste créé avec succès" });
    },
    onError: () => toast({ title: "Erreur", description: "Impossible de créer le poste.", variant: "destructive" }),
  });

  const createCandidateMutation = useMutation({
    mutationFn: () => createCandidate({ job_id: effectiveJobId!, ...newCandidate }),
    onSuccess: async (newCand) => {
      queryClient.invalidateQueries({ queryKey: ["recruitment", "candidates"] });
      setShowCreateCandidate(false);
      setNewCandidate({ first_name: "", last_name: "", email: "", phone: "", source: "" });
      toast({ title: "Candidat ajouté" });
      // Vérification doublon non-bloquante
      try {
        const { warnings } = await checkDuplicate(newCand.id);
        if (warnings.length > 0) {
          const w = warnings[0];
          toast({
            title: "Profil similaire détecté",
            description: `Un profil similaire existe déjà : ${w.first_name} ${w.last_name}${w.email ? ` (${w.email})` : ""}.`,
          });
        }
      } catch {
        // Ignorer les erreurs de check doublon
      }
    },
    onError: () => toast({ title: "Erreur", description: "Impossible de créer le candidat.", variant: "destructive" }),
  });

  const candidatesKey = ["recruitment", "candidates", effectiveJobId, searchText];

  const moveCandidateMutation = useMutation({
    mutationFn: ({ candidateId, stageId, reason, detail }: { candidateId: string; stageId: string; reason?: string; detail?: string }) =>
      moveCandidate(candidateId, { stage_id: stageId, rejection_reason: reason, rejection_reason_detail: detail }),
    onMutate: async ({ candidateId, stageId }) => {
      await queryClient.cancelQueries({ queryKey: candidatesKey });
      const prev = queryClient.getQueryData<Candidate[]>(candidatesKey);
      const targetStage = stages.find((s) => s.id === stageId);
      if (prev) {
        queryClient.setQueryData<Candidate[]>(candidatesKey, prev.map((c) =>
          c.id === candidateId
            ? { ...c, current_stage_id: stageId, current_stage_name: targetStage?.name ?? c.current_stage_name, current_stage_type: targetStage?.stage_type ?? c.current_stage_type }
            : c,
        ));
      }
      return { prev };
    },
    onError: (err: any, _vars, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(candidatesKey, ctx.prev);
      toast({ title: "Erreur", description: err?.response?.data?.detail || "Impossible de déplacer le candidat.", variant: "destructive" });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: candidatesKey });
      // Met aussi à jour les autres vues branchées sur les candidats recrutement
      // (sidebar badges, priorité du dashboard, etc.).
      queryClient.invalidateQueries({ queryKey: ["recruitment", "candidates"] });
      queryClient.invalidateQueries({ queryKey: ["recruitment", "timeline"] });
    },
  });

  const hireMutation = useMutation({
    mutationFn: ({
      candidateId,
      data,
      linkToEmployeeId,
      skipDuplicateCheck,
    }: {
      candidateId: string;
      data: typeof hireData;
      linkToEmployeeId?: string;
      skipDuplicateCheck?: boolean;
    }) =>
      hireCandidate(candidateId, {
        hire_date: data.hire_date,
        job_title: data.job_title || undefined,
        contract_type: data.contract_type,
        site: data.site || undefined,
        service: data.service_id.trim() || undefined,
        link_to_employee_id: linkToEmployeeId,
        skip_duplicate_check: skipDuplicateCheck,
      }),
    onSuccess: (res: HireResult) => {
      if (res.requires_confirmation) {
        setDuplicateEmployeeInfo({
          id: res.existing_employee_id!,
          first_name: res.existing_employee_first_name!,
          last_name: res.existing_employee_last_name!,
          email: res.existing_employee_email!,
        });
        setShowHireModal(false);
        setShowDuplicateEmployeeModal(true);
        return;
      }
      queryClient.invalidateQueries({ queryKey: ["recruitment"] });
      setShowHireModal(false);
      setHireCandidateId(null);
      setHireData({ hire_date: "", job_title: "", contract_type: "CDI", site: "", service_id: "" });
      toast({ title: "Embauche finalisée", description: res.message });
      if (res.employee_id) {
        setHireSuccessEmployeeId(res.employee_id);
      }
    },
    onError: (err: any) => {
      toast({ title: "Erreur", description: err?.response?.data?.detail || "Impossible de finaliser l'embauche.", variant: "destructive" });
    },
  });

  const createInterviewMutation = useMutation({
    mutationFn: () =>
      createInterview({
        candidate_id: selectedCandidate!.id,
        interview_type: interviewData.interview_type,
        scheduled_at: new Date(interviewData.scheduled_at).toISOString(),
        duration_minutes: interviewData.duration_minutes,
        location: interviewData.location || undefined,
        meeting_link: interviewData.meeting_link || undefined,
        ...(interviewParticipantIds.length > 0
          ? { participant_user_ids: interviewParticipantIds }
          : {}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recruitment", "interviews"] });
      queryClient.invalidateQueries({ queryKey: ["recruitment", "timeline"] });
      setShowInterviewModal(false);
      setInterviewData({ interview_type: "Entretien RH", scheduled_at: "", duration_minutes: 60, location: "", meeting_link: "" });
      setInterviewParticipantIds([]);
      toast({ title: "Entretien planifié" });
    },
    onError: () => toast({ title: "Erreur", description: "Impossible de planifier l'entretien.", variant: "destructive" }),
  });

  // ── Pipeline stage mutations (optimistic) ──

  const stagesKey = ["recruitment", "stages", effectiveJobId];

  const apiDetail = useCallback((err: unknown) => {
    const ax = err as { response?: { data?: { detail?: string } } };
    return ax?.response?.data?.detail;
  }, []);

  const renameStageMutation = useMutation({
    mutationFn: ({ stageId, name }: { stageId: string; name: string }) =>
      updatePipelineStage(effectiveJobId!, stageId, { name }),
    onMutate: async ({ stageId, name }) => {
      await queryClient.cancelQueries({ queryKey: stagesKey });
      const prev = queryClient.getQueryData<PipelineStage[]>(stagesKey);
      if (prev) {
        queryClient.setQueryData<PipelineStage[]>(stagesKey, prev.map((s) =>
          s.id === stageId ? { ...s, name } : s,
        ));
      }
      return { prev };
    },
    onError: (err: unknown, _v, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(stagesKey, ctx.prev);
      toast({ title: "Erreur", description: String(apiDetail(err) || "Impossible de renommer l'étape."), variant: "destructive" });
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: stagesKey }),
  });

  const addStageMutation = useMutation({
    mutationFn: (name: string) => createPipelineStage(effectiveJobId!, { name }),
    onMutate: async (name) => {
      await queryClient.cancelQueries({ queryKey: stagesKey });
      const prev = queryClient.getQueryData<PipelineStage[]>(stagesKey);
      if (prev) {
        const maxPos = prev.reduce((m, s) => Math.max(m, s.position), -1);
        const optimistic: PipelineStage = {
          id: `temp-${Date.now()}`,
          job_id: effectiveJobId!,
          name,
          position: maxPos + 1,
          is_final: false,
          stage_type: "standard",
        };
        queryClient.setQueryData<PipelineStage[]>(stagesKey, [...prev, optimistic]);
      }
      return { prev };
    },
    onError: (err: unknown, _v, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(stagesKey, ctx.prev);
      toast({ title: "Erreur", description: String(apiDetail(err) || "Impossible d'ajouter l'étape."), variant: "destructive" });
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: stagesKey }),
  });

  const removeStageMutation = useMutation({
    mutationFn: (stageId: string) => deletePipelineStage(effectiveJobId!, stageId),
    onMutate: async (stageId) => {
      await queryClient.cancelQueries({ queryKey: stagesKey });
      const prev = queryClient.getQueryData<PipelineStage[]>(stagesKey);
      if (prev) {
        queryClient.setQueryData<PipelineStage[]>(stagesKey, prev.filter((s) => s.id !== stageId));
      }
      return { prev };
    },
    onError: (err: unknown, _v, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(stagesKey, ctx.prev);
      toast({ title: "Erreur", description: String(apiDetail(err) || "Impossible de supprimer l'étape."), variant: "destructive" });
    },
    onSettled: () => {
      setDeleteStageTarget(null);
      queryClient.invalidateQueries({ queryKey: stagesKey });
    },
  });

  const reorderStagesMutation = useMutation({
    mutationFn: (ids: string[]) => reorderPipelineStages(effectiveJobId!, ids),
    onMutate: async (ids) => {
      await queryClient.cancelQueries({ queryKey: stagesKey });
      const prev = queryClient.getQueryData<PipelineStage[]>(stagesKey);
      if (prev) {
        const byId = Object.fromEntries(prev.map((s) => [s.id, s]));
        const reordered = ids.map((id, i) => ({ ...byId[id], position: i })).filter(Boolean) as PipelineStage[];
        const rest = prev.filter((s) => !ids.includes(s.id));
        queryClient.setQueryData<PipelineStage[]>(stagesKey, [...reordered, ...rest]);
      }
      return { prev };
    },
    onError: (err: unknown, _v, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(stagesKey, ctx.prev);
      toast({ title: "Erreur", description: String(apiDetail(err) || "Impossible de réordonner les étapes."), variant: "destructive" });
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: stagesKey }),
  });

  const sortedPipelineStages = useMemo(
    () => [...stages].sort((a, b) => a.position - b.position),
    [stages],
  );
  const standardStages = useMemo(
    () => sortedPipelineStages.filter((s) => s.stage_type === "standard"),
    [sortedPipelineStages],
  );
  const isInterviewStage = useCallback((stage: PipelineStage) => {
    const name = (stage.name || "").toLowerCase();
    return name.includes("entretien");
  }, []);
  const movableStandardStages = useMemo(
    () => standardStages.filter((s) => isInterviewStage(s)),
    [standardStages, isInterviewStage],
  );
  const terminalStages = useMemo(() => {
    const hired = sortedPipelineStages.find((s) => s.stage_type === "hired");
    const rejected = sortedPipelineStages.find((s) => s.stage_type === "rejected");
    return [hired, rejected].filter(Boolean) as PipelineStage[];
  }, [sortedPipelineStages]);
  const pipelineStageIds = useMemo(() => movableStandardStages.map((s) => s.id), [movableStandardStages]);

  const stageReorderSensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handlePipelineStageDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      if (!over || active.id === over.id) return;
      const sorted = [...movableStandardStages].sort((a, b) => a.position - b.position);
      const oldIndex = sorted.findIndex((s) => s.id === active.id);
      const newIndex = sorted.findIndex((s) => s.id === over.id);
      if (oldIndex < 0 || newIndex < 0) return;
      reorderStagesMutation.mutate(arrayMove(sorted, oldIndex, newIndex).map((s) => s.id));
    },
    [movableStandardStages, reorderStagesMutation],
  );

  // Grouped candidates by stage (fallback : 1re colonne standard si étape absente ou inconnue)
  const candidatesByStage = useMemo(() => {
    const map: Record<string, Candidate[]> = {};
    for (const s of stages) map[s.id] = [];
    const ordered = [...stages].sort((a, b) => a.position - b.position);
    const fallbackStageId =
      ordered.find((s) => s.stage_type === "standard")?.id ?? ordered[0]?.id;
    for (const c of candidates) {
      const sid = c.current_stage_id;
      if (sid && map[sid]) {
        map[sid].push(c);
      } else if (fallbackStageId) {
        map[fallbackStageId].push(c);
      }
    }
    return map;
  }, [stages, candidates]);

  const handleCardClick = (c: Candidate) => {
    setSelectedCandidate(c);
    setSlideOverOpen(true);
  };

  const handleDrop = (candidateId: string, stageId: string) => {
    const stage = stages.find((s) => s.id === stageId);
    if (!stage) return;
    if (stage.stage_type === "rejected") {
      setRejectCandidateId(candidateId);
      setRejectStageId(stageId);
      setShowRejectModal(true);
      return;
    }
    if (stage.stage_type === "hired") {
      setHireCandidateId(candidateId);
      setShowHireModal(true);
      return;
    }
    moveCandidateMutation.mutate({ candidateId, stageId });
  };

  const handleMoveFromSlideOver = (candidateId: string, stageId: string) => {
    const stage = stages.find((s) => s.id === stageId);
    if (!stage) return;
    if (stage.stage_type === "rejected") {
      setRejectCandidateId(candidateId);
      setRejectStageId(stageId);
      setShowRejectModal(true);
      return;
    }
    moveCandidateMutation.mutate({ candidateId, stageId });
  };

  const handleHireFromSlideOver = (candidateId: string) => {
    setHireCandidateId(candidateId);
    setShowHireModal(true);
  };

  const handleRequestReject = (candidateId: string) => {
    const rejectedStage = stages.find((s) => s.stage_type === "rejected");
    if (rejectedStage) {
      setRejectCandidateId(candidateId);
      setRejectStageId(rejectedStage.id);
      setShowRejectModal(true);
    }
  };

  const selectedJobData = jobs.find((j) => j.id === effectiveJobId);

  // ─── Render ─────────────────────────────────────────────────────

  if (loadingJobs) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="flex gap-4">
          {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-96 w-64" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Recrutement</h1>
          <p className="text-muted-foreground mt-1">Pipeline de candidatures et gestion des postes</p>
        </div>
        {isRh && (
          <Button onClick={() => setShowCreateJob(true)}>
            <Plus className="h-4 w-4 mr-2" /> Nouveau poste
          </Button>
        )}
      </div>

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
        {/* Job selector */}
        <Select
          value={effectiveJobId || ""}
          onValueChange={(v) => setSelectedJobId(v)}
        >
          <SelectTrigger className="w-[280px]">
            <Briefcase className="h-4 w-4 mr-2 text-muted-foreground" />
            <SelectValue placeholder="Sélectionner un poste" />
          </SelectTrigger>
          <SelectContent>
            {jobs.map((j) => (
              <SelectItem key={j.id} value={j.id}>
                <div className="flex items-center gap-2">
                  <span>{j.title}</span>
                  <Badge variant={j.status === "active" ? "default" : "secondary"} className="text-[10px] h-4">
                    {j.status === "active" ? "Actif" : j.status === "draft" ? "Brouillon" : "Archivé"}
                  </Badge>
                  {j.candidate_count !== undefined && (
                    <span className="text-xs text-muted-foreground">({j.candidate_count})</span>
                  )}
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Search */}
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Rechercher un candidat..."
            className="pl-9"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
          />
        </div>

        {isRh && (
          <div className="flex border rounded-lg h-9 shrink-0">
            <Button
              type="button"
              variant={mainSection === "pipeline" ? "default" : "ghost"}
              size="sm"
              className="rounded-r-none h-9 px-3"
              onClick={() => setMainSection("pipeline")}
            >
              Pipeline
            </Button>
            <Button
              type="button"
              variant={mainSection === "analytics" ? "default" : "ghost"}
              size="sm"
              className="rounded-l-none h-9 px-3 gap-1"
              onClick={() => setMainSection("analytics")}
            >
              <BarChart3 className="h-4 w-4" />
              Analytics
            </Button>
          </div>
        )}

        {/* View toggle (pipeline uniquement) */}
        {mainSection === "pipeline" && (
          <div className="flex border rounded-lg h-9 shrink-0">
            <Button
              variant={viewMode === "kanban" ? "default" : "ghost"}
              size="sm"
              className="rounded-r-none h-9"
              onClick={() => setViewMode("kanban")}
            >
              <LayoutGrid className="h-4 w-4" />
            </Button>
            <Button
              variant={viewMode === "list" ? "default" : "ghost"}
              size="sm"
              className="rounded-l-none h-9"
              onClick={() => setViewMode("list")}
            >
              <List className="h-4 w-4" />
            </Button>
          </div>
        )}

        {isRh && effectiveJobId && (
          <Button onClick={() => setShowCreateCandidate(true)} size="sm">
            <UserPlus className="h-4 w-4 mr-1" /> Nouveau candidat
          </Button>
        )}
      </div>

      {/* Content */}
      {mainSection === "analytics" && isRh ? (
        <RecruitmentAnalyticsSection companyId={companyId} jobs={jobs} />
      ) : !effectiveJobId ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <Briefcase className="h-12 w-12 text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-medium mb-1">Aucun poste</h3>
            <p className="text-muted-foreground text-sm mb-4">Créez un poste pour commencer à recruter.</p>
            {isRh && (
              <Button onClick={() => setShowCreateJob(true)}>
                <Plus className="h-4 w-4 mr-2" /> Créer un poste
              </Button>
            )}
          </CardContent>
        </Card>
      ) : loadingStages || loadingCandidates ? (
        <div className="flex gap-4 overflow-x-auto rounded-lg bg-muted/30 p-2 pb-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-80 min-w-[260px]" />
          ))}
        </div>
      ) : viewMode === "kanban" ? (
        <div className="space-y-2">
          <PipelineStageSummaryRow
            stages={sortedPipelineStages}
            candidatesByStage={candidatesByStage}
          />
          <div
            className={cn(
              "flex overflow-x-auto scroll-smooth rounded-lg bg-muted/30 p-2 pb-4 items-stretch",
              isRh && "gap-2",
            )}
          >
          {isRh ? (
            <>
              <DndContext
                sensors={stageReorderSensors}
                collisionDetection={closestCenter}
                onDragEnd={handlePipelineStageDragEnd}
              >
                <SortableContext items={pipelineStageIds} strategy={horizontalListSortingStrategy}>
                  {standardStages.map((stage) => (
                    isInterviewStage(stage) ? (
                      <SortableStageColumn
                        key={stage.id}
                        stage={stage}
                        candidates={candidatesByStage[stage.id] || []}
                        onCardClick={handleCardClick}
                        onCandidateDrop={handleDrop}
                        isRh={isRh}
                        onRename={(name) => renameStageMutation.mutate({ stageId: stage.id, name })}
                        onDelete={stage.stage_type === "standard" ? () => setDeleteStageTarget(stage) : undefined}
                      />
                    ) : (
                      <div
                        key={stage.id}
                        id={`recruitment-pipeline-stage-${stage.id}`}
                        className="shrink-0"
                      >
                        <KanbanColumn
                          stage={stage}
                          candidates={candidatesByStage[stage.id] || []}
                          onCardClick={handleCardClick}
                          onCandidateDrop={handleDrop}
                          isRh={isRh}
                          onRename={(name) => renameStageMutation.mutate({ stageId: stage.id, name })}
                          onDelete={stage.stage_type === "standard" ? () => setDeleteStageTarget(stage) : undefined}
                        />
                      </div>
                    )
                  ))}
                </SortableContext>
              </DndContext>
              {terminalStages.length > 0 && (
                <div className="shrink-0 ml-2 border-l pl-2 space-y-3">
                  {terminalStages.map((stage) => (
                    <div key={stage.id} id={`recruitment-pipeline-stage-${stage.id}`}>
                      <KanbanColumn
                        stage={stage}
                        candidates={candidatesByStage[stage.id] || []}
                        onCardClick={handleCardClick}
                        onCandidateDrop={handleDrop}
                        isRh={isRh}
                      />
                    </div>
                  ))}
                </div>
              )}
              <AddStageColumn onAdd={(name) => addStageMutation.mutate(name)} />
            </>
          ) : (
            <>
              {standardStages.map((stage, idx) => (
                <div
                  key={stage.id}
                  id={`recruitment-pipeline-stage-${stage.id}`}
                  className={cn("shrink-0", idx > 0 && "ml-3")}
                >
                  <KanbanColumn
                    stage={stage}
                    candidates={candidatesByStage[stage.id] || []}
                    onCardClick={handleCardClick}
                    onCandidateDrop={handleDrop}
                    isRh={isRh}
                  />
                </div>
              ))}
              {terminalStages.length > 0 && (
                <div className="shrink-0 ml-3 border-l pl-3 space-y-3">
                  {terminalStages.map((stage) => (
                    <div key={stage.id} id={`recruitment-pipeline-stage-${stage.id}`}>
                      <KanbanColumn
                        stage={stage}
                        candidates={candidatesByStage[stage.id] || []}
                        onCardClick={handleCardClick}
                        onCandidateDrop={handleDrop}
                        isRh={isRh}
                      />
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
          </div>
        </div>
      ) : (
        /* LIST VIEW */
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Candidat</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Téléphone</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Étape</TableHead>
                <TableHead>Date</TableHead>
                {isRh && <TableHead className="text-right">Actions</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {candidates.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={isRh ? 7 : 6} className="text-center py-8 text-muted-foreground">
                    Aucun candidat pour ce poste. Ajoutez un candidat pour démarrer.
                  </TableCell>
                </TableRow>
              ) : (
                candidates.map((c) => (
                  <TableRow
                    key={c.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => handleCardClick(c)}
                  >
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Avatar className="h-7 w-7">
                          <AvatarFallback className="text-xs bg-primary/10 text-primary">
                            {c.first_name[0]}{c.last_name[0]}
                          </AvatarFallback>
                        </Avatar>
                        <span className="font-medium text-sm">{c.first_name} {c.last_name}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">{c.email || "—"}</TableCell>
                    <TableCell className="text-sm">{c.phone || "—"}</TableCell>
                    <TableCell className="text-sm">{c.source || "—"}</TableCell>
                    <TableCell>
                      <Badge
                        variant={c.current_stage_type === "rejected" ? "destructive" : c.current_stage_type === "hired" ? "default" : "secondary"}
                        className="text-xs"
                      >
                        {c.current_stage_name || "—"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(c.created_at).toLocaleDateString("fr-FR")}
                    </TableCell>
                    {isRh && (
                      <TableCell className="text-right">
                        <Select
                          onValueChange={(stageId) => handleDrop(c.id, stageId)}
                        >
                          <SelectTrigger className="w-[140px] h-7 text-xs">
                            <SelectValue placeholder="Déplacer..." />
                          </SelectTrigger>
                          <SelectContent>
                            {stages
                              .filter((s) => s.id !== c.current_stage_id)
                              .map((s) => (
                                <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                              ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                    )}
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </Card>
      )}

      {/* Slide-over */}
      <CandidateSlideOver
        candidate={selectedCandidate}
        open={slideOverOpen}
        onClose={() => {
          setSlideOverOpen(false);
          setSelectedCandidate(null);
        }}
        isRh={isRh}
        stages={stages}
        onMove={handleMoveFromSlideOver}
        onHire={handleHireFromSlideOver}
        onRequestReject={handleRequestReject}
        onScheduleInterview={() => setShowInterviewModal(true)}
        companyId={companyId}
        onCandidateRefresh={(c) => setSelectedCandidate(c)}
      />

      {/* Confirmation : Supprimer une étape */}
      <AlertDialog open={!!deleteStageTarget} onOpenChange={(o) => !o && setDeleteStageTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer l&apos;étape « {deleteStageTarget?.name} » ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action est irréversible. L&apos;étape sera supprimée du pipeline.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(e) => {
                e.preventDefault();
                if (deleteStageTarget) removeStageMutation.mutate(deleteStageTarget.id);
              }}
            >
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Dialog : Créer un poste */}
      <Dialog open={showCreateJob} onOpenChange={setShowCreateJob}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Nouveau poste</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Titre du poste *</Label>
              <Input value={newJob.title} onChange={(e) => setNewJob({ ...newJob, title: e.target.value })} placeholder="Ex: Développeur Full Stack" />
            </div>
            <div>
              <Label>Description</Label>
              <Textarea value={newJob.description} onChange={(e) => setNewJob({ ...newJob, description: e.target.value })} placeholder="Description du poste..." />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Localisation</Label>
                <Input value={newJob.location} onChange={(e) => setNewJob({ ...newJob, location: e.target.value })} placeholder="Paris" />
              </div>
              <div>
                <Label>Type de contrat</Label>
                <Select value={newJob.contract_type} onValueChange={(v) => setNewJob({ ...newJob, contract_type: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {["CDI", "CDD", "Alternance", "Stage", "Intérim", "Freelance", "Autre"].map((t) => (
                      <SelectItem key={t} value={t}>{t}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateJob(false)}>Annuler</Button>
            <Button
              onClick={() => createJobMutation.mutate()}
              disabled={!newJob.title.trim() || createJobMutation.isPending}
            >
              {createJobMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Créer le poste
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog : Créer un candidat */}
      <Dialog open={showCreateCandidate} onOpenChange={setShowCreateCandidate}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Nouveau candidat</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Prénom *</Label>
                <Input value={newCandidate.first_name} onChange={(e) => setNewCandidate({ ...newCandidate, first_name: e.target.value })} />
              </div>
              <div>
                <Label>Nom *</Label>
                <Input value={newCandidate.last_name} onChange={(e) => setNewCandidate({ ...newCandidate, last_name: e.target.value })} />
              </div>
            </div>
            <div>
              <Label>Email</Label>
              <Input type="email" value={newCandidate.email} onChange={(e) => setNewCandidate({ ...newCandidate, email: e.target.value })} />
            </div>
            <div>
              <Label>Téléphone</Label>
              <Input value={newCandidate.phone} onChange={(e) => setNewCandidate({ ...newCandidate, phone: e.target.value })} />
            </div>
            <div>
              <Label>Source</Label>
              <Input value={newCandidate.source} onChange={(e) => setNewCandidate({ ...newCandidate, source: e.target.value })} placeholder="LinkedIn, Indeed, Cooptation..." />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateCandidate(false)}>Annuler</Button>
            <Button
              onClick={() => createCandidateMutation.mutate()}
              disabled={!newCandidate.first_name.trim() || !newCandidate.last_name.trim() || createCandidateMutation.isPending}
            >
              {createCandidateMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Ajouter le candidat
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog : Refus */}
      <Dialog open={showRejectModal} onOpenChange={setShowRejectModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              Refuser le candidat
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Motif de refus *</Label>
              <Select value={rejectReason} onValueChange={setRejectReason}>
                <SelectTrigger><SelectValue placeholder="Sélectionner un motif" /></SelectTrigger>
                <SelectContent>
                  {(rejectionReasons?.reasons || []).map((r) => (
                    <SelectItem key={r} value={r}>{r}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {rejectReason === "Autre" && (
              <div>
                <Label>Précisez</Label>
                <Textarea value={rejectDetail} onChange={(e) => setRejectDetail(e.target.value)} />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setShowRejectModal(false); setRejectReason(""); setRejectDetail(""); }}>Annuler</Button>
            <Button
              variant="destructive"
              disabled={!rejectReason || moveCandidateMutation.isPending}
              onClick={() => {
                if (rejectCandidateId && rejectStageId) {
                  moveCandidateMutation.mutate({
                    candidateId: rejectCandidateId,
                    stageId: rejectStageId,
                    reason: rejectReason,
                    detail: rejectReason === "Autre" ? rejectDetail : undefined,
                  });
                  setShowRejectModal(false);
                  setRejectCandidateId(null);
                  setRejectStageId(null);
                  setRejectReason("");
                  setRejectDetail("");
                }
              }}
            >
              Confirmer le refus
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog : Embauche */}
      <Dialog open={showHireModal} onOpenChange={setShowHireModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <UserPlus className="h-5 w-5 text-green-600" />
              Marquer comme recruté — Créer le salarié
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Date d'entrée *</Label>
              <Input type="date" value={hireData.hire_date} onChange={(e) => setHireData({ ...hireData, hire_date: e.target.value })} />
            </div>
            <div>
              <Label>Intitulé du poste</Label>
              <Input value={hireData.job_title} onChange={(e) => setHireData({ ...hireData, job_title: e.target.value })} placeholder={selectedJobData?.title} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Type de contrat</Label>
                <Select value={hireData.contract_type} onValueChange={(v) => setHireData({ ...hireData, contract_type: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {["CDI", "CDD", "Alternance", "Stage", "Intérim"].map((t) => (
                      <SelectItem key={t} value={t}>{t}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Établissement / Site</Label>
                <Input value={hireData.site} onChange={(e) => setHireData({ ...hireData, site: e.target.value })} placeholder="Siège, Paris..." />
              </div>
            </div>
            <div>
              <Label>Service / Département</Label>
              <Select
                value={hireData.service_id ? hireData.service_id : "__none__"}
                onValueChange={(v) =>
                  setHireData({ ...hireData, service_id: v === "__none__" ? "" : v })
                }
                disabled={servicesQuery.isLoading}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Aucun service" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Aucun service</SelectItem>
                  {(servicesQuery.data ?? []).map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setShowHireModal(false); setHireCandidateId(null); }}>Annuler</Button>
            <Button
              className="bg-green-600 hover:bg-green-700"
              disabled={!hireData.hire_date || hireMutation.isPending}
              onClick={() => {
                if (hireCandidateId) {
                  hireMutation.mutate({ candidateId: hireCandidateId, data: hireData });
                }
              }}
            >
              {hireMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Créer le salarié
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!hireSuccessEmployeeId}
        onOpenChange={(open) => {
          if (!open) setHireSuccessEmployeeId(null);
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Onboarding</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Une checklist d&apos;onboarding a été créée pour le nouveau collaborateur. Vous pouvez la
            suivre depuis l&apos;espace dédié.
          </p>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" type="button" onClick={() => setHireSuccessEmployeeId(null)}>
              Fermer
            </Button>
            <Button
              type="button"
              onClick={() => {
                if (hireSuccessEmployeeId) {
                  navigate(`/onboarding/${hireSuccessEmployeeId}`);
                  setHireSuccessEmployeeId(null);
                }
              }}
            >
              Voir l&apos;onboarding
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog : Doublon salarié lors de l'embauche */}
      <Dialog open={showDuplicateEmployeeModal} onOpenChange={setShowDuplicateEmployeeModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              Salarié existant détecté
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Un salarié avec cet email existe déjà dans votre entreprise :
            </p>
            {duplicateEmployeeInfo && (
              <div className="border rounded-lg p-3 bg-muted/50">
                <p className="text-sm font-medium">{duplicateEmployeeInfo.first_name} {duplicateEmployeeInfo.last_name}</p>
                <p className="text-xs text-muted-foreground">{duplicateEmployeeInfo.email}</p>
              </div>
            )}
            <p className="text-sm">Que souhaitez-vous faire ?</p>
          </div>
          <DialogFooter className="flex flex-col gap-2 sm:flex-row">
            <Button
              variant="outline"
              className="flex-1"
              disabled={hireMutation.isPending}
              onClick={() => {
                if (hireCandidateId) {
                  hireMutation.mutate({
                    candidateId: hireCandidateId,
                    data: hireData,
                    skipDuplicateCheck: true,
                  });
                  setShowDuplicateEmployeeModal(false);
                  setDuplicateEmployeeInfo(null);
                }
              }}
            >
              {hireMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Créer une nouvelle fiche
            </Button>
            <Button
              className="flex-1 bg-green-600 hover:bg-green-700"
              disabled={hireMutation.isPending}
              onClick={() => {
                if (hireCandidateId && duplicateEmployeeInfo) {
                  hireMutation.mutate({
                    candidateId: hireCandidateId,
                    data: hireData,
                    linkToEmployeeId: duplicateEmployeeInfo.id,
                  });
                  setShowDuplicateEmployeeModal(false);
                  setDuplicateEmployeeInfo(null);
                }
              }}
            >
              {hireMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Lier au salarié existant
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog : Planifier entretien (accessible depuis slide-over actions) */}
      <Dialog open={showInterviewModal} onOpenChange={setShowInterviewModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Planifier un entretien</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Type d'entretien</Label>
              <Select value={interviewData.interview_type} onValueChange={(v) => setInterviewData({ ...interviewData, interview_type: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["Entretien RH", "Entretien technique", "Entretien manager", "Entretien final", "Appel téléphonique"].map((t) => (
                    <SelectItem key={t} value={t}>{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Date et heure *</Label>
              <Input type="datetime-local" value={interviewData.scheduled_at} onChange={(e) => setInterviewData({ ...interviewData, scheduled_at: e.target.value })} />
            </div>
            <div>
              <Label>Durée (minutes)</Label>
              <Input type="number" value={interviewData.duration_minutes} onChange={(e) => setInterviewData({ ...interviewData, duration_minutes: parseInt(e.target.value) || 60 })} />
            </div>
            <div>
              <Label>Lieu</Label>
              <Input value={interviewData.location} onChange={(e) => setInterviewData({ ...interviewData, location: e.target.value })} placeholder="Bureau, salle de réunion..." />
            </div>
            <div>
              <Label>Lien visioconférence</Label>
              <Input value={interviewData.meeting_link} onChange={(e) => setInterviewData({ ...interviewData, meeting_link: e.target.value })} placeholder="https://meet.google.com/..." />
            </div>
            <div className="space-y-2">
              <Label>Participants</Label>
              <p className="text-xs text-muted-foreground">
                Utilisateurs invités comme intervieweurs (même liste que la gestion des utilisateurs).
              </p>
              <ScrollArea className="h-[200px] rounded-md border bg-muted/20">
                <div className="p-3 space-y-2">
                  {loadingInterviewCompanyUsers ? (
                    <>
                      <Skeleton className="h-9 w-full" />
                      <Skeleton className="h-9 w-full" />
                      <Skeleton className="h-9 w-full" />
                    </>
                  ) : interviewCompanyUsers.length === 0 ? (
                    <p className="text-xs text-muted-foreground py-2">
                      Aucun utilisateur chargé pour cette entreprise.
                    </p>
                  ) : (
                    interviewCompanyUsers.map((u) => {
                      const label =
                        `${u.first_name ?? ""} ${u.last_name ?? ""}`.trim() || u.email || u.id;
                      return (
                        <label
                          key={u.id}
                          htmlFor={`interview-participant-${u.id}`}
                          className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted/80 cursor-pointer"
                        >
                          <Checkbox
                            id={`interview-participant-${u.id}`}
                            checked={interviewParticipantIds.includes(u.id)}
                            onCheckedChange={(checked) => {
                              setInterviewParticipantIds((prev) =>
                                checked === true
                                  ? prev.includes(u.id)
                                    ? prev
                                    : [...prev, u.id]
                                  : prev.filter((id) => id !== u.id),
                              );
                            }}
                          />
                          <span className="truncate">{label}</span>
                        </label>
                      );
                    })
                  )}
                </div>
              </ScrollArea>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowInterviewModal(false)}>Annuler</Button>
            <Button
              disabled={!interviewData.scheduled_at || createInterviewMutation.isPending}
              onClick={() => createInterviewMutation.mutate()}
            >
              {createInterviewMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Planifier
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

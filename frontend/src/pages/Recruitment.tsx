// frontend/src/pages/Recruitment.tsx
// Page RH : Module Recrutement (ATS) — Pipeline Kanban + Vue Liste + Fiche candidat

import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getJobs, createJob, getPipelineStages, getCandidates, createCandidate,
  moveCandidate, getCandidate, getNotes, createNote, getOpinions, createOpinion,
  getInterviews, createInterview, getTimeline, hireCandidate, getRejectionReasons,
  deleteCandidate,
  type Job, type PipelineStage, type Candidate, type Note, type Opinion,
  type Interview, type TimelineEvent,
} from "@/api/recruitment";
import { useAuth } from "@/contexts/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useToast } from "@/components/ui/use-toast";
import {
  Plus, Search, LayoutGrid, List, User, Mail, Phone, Calendar,
  Clock, MapPin, Link2, FileText, ThumbsUp, ThumbsDown, ArrowRight,
  Loader2, Briefcase, X, ChevronRight, MessageSquare, AlertTriangle,
  UserPlus, GripVertical,
} from "lucide-react";

// ─── Kanban Card ────────────────────────────────────────────────────

function CandidateCard({ candidate, onClick }: { candidate: Candidate; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      className="bg-white border rounded-lg p-3 cursor-pointer hover:shadow-md transition-shadow group"
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
    </div>
  );
}

// ─── Kanban Column ──────────────────────────────────────────────────

function KanbanColumn({
  stage,
  candidates,
  onCardClick,
  onDrop,
  isRh,
}: {
  stage: PipelineStage;
  candidates: Candidate[];
  onCardClick: (c: Candidate) => void;
  onDrop: (candidateId: string, stageId: string) => void;
  isRh: boolean;
}) {
  const bgColor = stage.stage_type === "rejected"
    ? "border-red-200 bg-red-50/50"
    : stage.stage_type === "hired"
      ? "border-green-200 bg-green-50/50"
      : "border-border bg-muted/30";

  return (
    <div
      className={`flex flex-col min-w-[260px] max-w-[300px] rounded-lg border ${bgColor}`}
      onDragOver={isRh ? (e) => e.preventDefault() : undefined}
      onDrop={isRh ? (e) => {
        e.preventDefault();
        const candidateId = e.dataTransfer.getData("candidateId");
        if (candidateId) onDrop(candidateId, stage.id);
      } : undefined}
    >
      <div className="px-3 py-2.5 border-b flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">{stage.name}</span>
          <Badge variant="secondary" className="h-5 text-[10px] px-1.5">
            {candidates.length}
          </Badge>
        </div>
      </div>
      <ScrollArea className="flex-1 p-2 max-h-[calc(100vh-320px)]">
        <div className="space-y-2">
          {candidates.map((c) => (
            <div
              key={c.id}
              draggable={isRh}
              onDragStart={isRh ? (e) => e.dataTransfer.setData("candidateId", c.id) : undefined}
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

// ─── Candidate Slide-over ───────────────────────────────────────────

function CandidateSlideOver({
  candidate,
  open,
  onClose,
  isRh,
  stages,
  onMove,
  onHire,
}: {
  candidate: Candidate | null;
  open: boolean;
  onClose: () => void;
  isRh: boolean;
  stages: PipelineStage[];
  onMove: (candidateId: string, stageId: string, reason?: string) => void;
  onHire: (candidateId: string) => void;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [noteText, setNoteText] = useState("");
  const [opinionRating, setOpinionRating] = useState<"favorable" | "defavorable" | null>(null);
  const [opinionComment, setOpinionComment] = useState("");
  const [activeTab, setActiveTab] = useState("info");

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

  const addNoteMutation = useMutation({
    mutationFn: (content: string) => createNote({ candidate_id: candidateId!, content }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recruitment", "notes", candidateId] });
      queryClient.invalidateQueries({ queryKey: ["recruitment", "timeline", candidateId] });
      setNoteText("");
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

  if (!candidate) return null;

  const currentStage = stages.find((s) => s.id === candidate.current_stage_id);
  const favorableCount = opinions.filter((o) => o.rating === "favorable").length;
  const defavorableCount = opinions.filter((o) => o.rating === "defavorable").length;

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent className="w-full sm:max-w-xl overflow-y-auto p-0">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-background border-b px-6 py-4">
          <SheetHeader className="mb-0">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Avatar className="h-10 w-10">
                  <AvatarFallback className="bg-primary/10 text-primary font-semibold">
                    {candidate.first_name[0]}{candidate.last_name[0]}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <SheetTitle className="text-lg">{candidate.first_name} {candidate.last_name}</SheetTitle>
                  {currentStage && (
                    <Badge
                      variant={currentStage.stage_type === "rejected" ? "destructive" : currentStage.stage_type === "hired" ? "default" : "secondary"}
                      className="mt-0.5"
                    >
                      {currentStage.name}
                    </Badge>
                  )}
                </div>
              </div>
            </div>
          </SheetHeader>

          {/* Actions RH */}
          {isRh && currentStage?.stage_type !== "rejected" && currentStage?.stage_type !== "hired" && (
            <div className="flex gap-2 mt-3">
              <Select
                onValueChange={(stageId) => onMove(candidate.id, stageId)}
              >
                <SelectTrigger className="w-[200px] h-8 text-xs">
                  <SelectValue placeholder="Déplacer vers..." />
                </SelectTrigger>
                <SelectContent>
                  {stages
                    .filter((s) => s.id !== candidate.current_stage_id && s.stage_type !== "rejected" && s.stage_type !== "hired")
                    .map((s) => (
                      <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                    ))}
                </SelectContent>
              </Select>
              <Button
                size="sm"
                variant="destructive"
                className="h-8 text-xs"
                onClick={() => {
                  const rejectedStage = stages.find((s) => s.stage_type === "rejected");
                  if (rejectedStage) onMove(candidate.id, rejectedStage.id, "Profil non adapté");
                }}
              >
                Refuser
              </Button>
              <Button
                size="sm"
                className="h-8 text-xs bg-green-600 hover:bg-green-700"
                onClick={() => onHire(candidate.id)}
              >
                Recruter
              </Button>
            </div>
          )}
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="px-6 pt-4">
          <TabsList className="w-full grid grid-cols-4">
            <TabsTrigger value="info">Infos</TabsTrigger>
            <TabsTrigger value="notes">Notes ({notes.length})</TabsTrigger>
            <TabsTrigger value="interviews">Entretiens ({interviews.length})</TabsTrigger>
            <TabsTrigger value="timeline">Timeline</TabsTrigger>
          </TabsList>

          {/* Tab Infos */}
          <TabsContent value="info" className="space-y-4 mt-4">
            <div className="grid gap-3">
              {candidate.email && (
                <div className="flex items-center gap-2 text-sm">
                  <Mail className="h-4 w-4 text-muted-foreground" />
                  <a href={`mailto:${candidate.email}`} className="text-primary hover:underline">{candidate.email}</a>
                </div>
              )}
              {candidate.phone && (
                <div className="flex items-center gap-2 text-sm">
                  <Phone className="h-4 w-4 text-muted-foreground" />
                  <span>{candidate.phone}</span>
                </div>
              )}
              {candidate.source && (
                <div className="flex items-center gap-2 text-sm">
                  <Briefcase className="h-4 w-4 text-muted-foreground" />
                  <span>Source : {candidate.source}</span>
                </div>
              )}
              <div className="flex items-center gap-2 text-sm">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <span>Ajouté le {new Date(candidate.created_at).toLocaleDateString("fr-FR")}</span>
              </div>
            </div>

            {/* Opinions summary */}
            <Separator />
            <div>
              <h4 className="text-sm font-semibold mb-3">Avis ({opinions.length})</h4>
              <div className="flex gap-4 mb-3">
                <div className="flex items-center gap-1.5">
                  <ThumbsUp className="h-4 w-4 text-green-600" />
                  <span className="text-sm font-medium">{favorableCount} favorable{favorableCount > 1 ? "s" : ""}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <ThumbsDown className="h-4 w-4 text-red-500" />
                  <span className="text-sm font-medium">{defavorableCount} défavorable{defavorableCount > 1 ? "s" : ""}</span>
                </div>
              </div>
              {opinions.map((o) => (
                <div key={o.id} className="flex items-start gap-2 mb-2">
                  <Badge variant={o.rating === "favorable" ? "default" : "destructive"} className="text-[10px] flex-shrink-0 mt-0.5">
                    {o.rating === "favorable" ? "+" : "-"}
                  </Badge>
                  <div className="text-xs">
                    <span className="font-medium">{o.author_first_name} {o.author_last_name}</span>
                    {o.comment && <span className="text-muted-foreground"> — {o.comment}</span>}
                  </div>
                </div>
              ))}
              {/* Add opinion */}
              <div className="mt-3 space-y-2 p-3 bg-muted/50 rounded-lg">
                <p className="text-xs font-medium">Donner un avis</p>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant={opinionRating === "favorable" ? "default" : "outline"}
                    className="h-7 text-xs"
                    onClick={() => setOpinionRating("favorable")}
                  >
                    <ThumbsUp className="h-3 w-3 mr-1" /> Favorable
                  </Button>
                  <Button
                    size="sm"
                    variant={opinionRating === "defavorable" ? "destructive" : "outline"}
                    className="h-7 text-xs"
                    onClick={() => setOpinionRating("defavorable")}
                  >
                    <ThumbsDown className="h-3 w-3 mr-1" /> Défavorable
                  </Button>
                </div>
                {opinionRating && (
                  <>
                    <Input
                      placeholder="Commentaire (optionnel)"
                      className="h-8 text-xs"
                      value={opinionComment}
                      onChange={(e) => setOpinionComment(e.target.value)}
                    />
                    <Button
                      size="sm"
                      className="h-7 text-xs"
                      disabled={addOpinionMutation.isPending}
                      onClick={() => addOpinionMutation.mutate({ rating: opinionRating, comment: opinionComment || undefined })}
                    >
                      {addOpinionMutation.isPending && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}
                      Valider
                    </Button>
                  </>
                )}
              </div>
            </div>
          </TabsContent>

          {/* Tab Notes */}
          <TabsContent value="notes" className="space-y-4 mt-4">
            <div className="space-y-2 p-3 bg-muted/50 rounded-lg">
              <Textarea
                placeholder="Ajouter une note..."
                className="text-sm min-h-[60px]"
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
              />
              <Button
                size="sm"
                className="h-8 text-xs"
                disabled={!noteText.trim() || addNoteMutation.isPending}
                onClick={() => addNoteMutation.mutate(noteText.trim())}
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
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium">{n.author_first_name} {n.author_last_name}</span>
                      <span className="text-[10px] text-muted-foreground">
                        {new Date(n.created_at).toLocaleDateString("fr-FR")} à {new Date(n.created_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                    <p className="text-sm whitespace-pre-wrap">{n.content}</p>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>

          {/* Tab Entretiens */}
          <TabsContent value="interviews" className="space-y-4 mt-4">
            {loadingInterviews ? (
              <div className="space-y-2">{[1, 2].map((i) => <Skeleton key={i} className="h-20" />)}</div>
            ) : interviews.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">Aucun entretien planifié.</p>
            ) : (
              <div className="space-y-3">
                {interviews.map((i) => (
                  <div key={i.id} className="border rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium">{i.interview_type}</span>
                      <Badge variant={i.status === "completed" ? "default" : i.status === "cancelled" ? "destructive" : "secondary"} className="text-[10px]">
                        {i.status === "planned" ? "Planifié" : i.status === "completed" ? "Terminé" : "Annulé"}
                      </Badge>
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {new Date(i.scheduled_at).toLocaleDateString("fr-FR")}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(i.scheduled_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })} · {i.duration_minutes}min
                      </span>
                      {i.location && (
                        <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{i.location}</span>
                      )}
                      {i.meeting_link && (
                        <a href={i.meeting_link} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-primary hover:underline">
                          <Link2 className="h-3 w-3" />Lien
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
                    {i.summary && (
                      <p className="text-xs mt-2 bg-muted/50 p-2 rounded">{i.summary}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </TabsContent>

          {/* Tab Timeline */}
          <TabsContent value="timeline" className="mt-4">
            {loadingTimeline ? (
              <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}</div>
            ) : timeline.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">Aucun événement.</p>
            ) : (
              <div className="relative pl-4 border-l-2 border-muted space-y-4 pb-6">
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
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────

export default function Recruitment() {
  const { user } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();

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
  const [hireCandidateId, setHireCandidateId] = useState<string | null>(null);
  const [rejectCandidateId, setRejectCandidateId] = useState<string | null>(null);
  const [rejectStageId, setRejectStageId] = useState<string | null>(null);

  // Forms state
  const [newJob, setNewJob] = useState({ title: "", description: "", location: "", contract_type: "CDI", status: "active" });
  const [newCandidate, setNewCandidate] = useState({ first_name: "", last_name: "", email: "", phone: "", source: "" });
  const [hireData, setHireData] = useState({ hire_date: "", job_title: "", contract_type: "CDI" });
  const [rejectReason, setRejectReason] = useState("");
  const [rejectDetail, setRejectDetail] = useState("");
  const [interviewData, setInterviewData] = useState({ interview_type: "Entretien RH", scheduled_at: "", duration_minutes: 60, location: "", meeting_link: "" });

  const isRh = user?.role === "rh" || user?.role === "admin" || user?.role === "collaborateur_rh";

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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recruitment", "candidates"] });
      setShowCreateCandidate(false);
      setNewCandidate({ first_name: "", last_name: "", email: "", phone: "", source: "" });
      toast({ title: "Candidat ajouté" });
    },
    onError: () => toast({ title: "Erreur", description: "Impossible de créer le candidat.", variant: "destructive" }),
  });

  const moveCandidateMutation = useMutation({
    mutationFn: ({ candidateId, stageId, reason, detail }: { candidateId: string; stageId: string; reason?: string; detail?: string }) =>
      moveCandidate(candidateId, { stage_id: stageId, rejection_reason: reason, rejection_reason_detail: detail }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recruitment", "candidates"] });
      queryClient.invalidateQueries({ queryKey: ["recruitment", "timeline"] });
      toast({ title: "Candidat déplacé" });
    },
    onError: (err: any) => {
      toast({ title: "Erreur", description: err?.response?.data?.detail || "Impossible de déplacer le candidat.", variant: "destructive" });
    },
  });

  const hireMutation = useMutation({
    mutationFn: ({ candidateId, data }: { candidateId: string; data: typeof hireData }) =>
      hireCandidate(candidateId, data),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["recruitment"] });
      setShowHireModal(false);
      setHireCandidateId(null);
      setHireData({ hire_date: "", job_title: "", contract_type: "CDI" });
      toast({ title: "Embauche finalisée", description: res.message });
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
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recruitment", "interviews"] });
      queryClient.invalidateQueries({ queryKey: ["recruitment", "timeline"] });
      setShowInterviewModal(false);
      setInterviewData({ interview_type: "Entretien RH", scheduled_at: "", duration_minutes: 60, location: "", meeting_link: "" });
      toast({ title: "Entretien planifié" });
    },
    onError: () => toast({ title: "Erreur", description: "Impossible de planifier l'entretien.", variant: "destructive" }),
  });

  // Grouped candidates by stage
  const candidatesByStage = useMemo(() => {
    const map: Record<string, Candidate[]> = {};
    for (const s of stages) map[s.id] = [];
    for (const c of candidates) {
      if (c.current_stage_id && map[c.current_stage_id]) {
        map[c.current_stage_id].push(c);
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

  const handleMoveFromSlideOver = (candidateId: string, stageId: string, reason?: string) => {
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
    const hiredStage = stages.find((s) => s.stage_type === "hired");
    if (hiredStage) {
      moveCandidateMutation.mutate({ candidateId, stageId: hiredStage.id });
    }
    setHireCandidateId(candidateId);
    setShowHireModal(true);
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

        {/* View toggle */}
        <div className="flex border rounded-lg">
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

        {isRh && effectiveJobId && (
          <Button onClick={() => setShowCreateCandidate(true)} size="sm">
            <UserPlus className="h-4 w-4 mr-1" /> Nouveau candidat
          </Button>
        )}
      </div>

      {/* Content */}
      {!effectiveJobId ? (
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
        <div className="flex gap-4 overflow-x-auto pb-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-80 min-w-[260px]" />
          ))}
        </div>
      ) : viewMode === "kanban" ? (
        /* KANBAN VIEW */
        <div className="flex gap-3 overflow-x-auto pb-4">
          {stages.map((stage) => (
            <KanbanColumn
              key={stage.id}
              stage={stage}
              candidates={candidatesByStage[stage.id] || []}
              onCardClick={handleCardClick}
              onDrop={handleDrop}
              isRh={isRh}
            />
          ))}
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
      />

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

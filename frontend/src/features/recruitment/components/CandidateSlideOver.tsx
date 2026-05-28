import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useToast } from "@/components/ui/use-toast";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Mail, Phone, Calendar, ThumbsUp, ThumbsDown, Loader2, Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  getNotes, createNote, getOpinions, createOpinion,
  getInterviews, getTimeline, deleteCandidate,
  uploadCandidateCV, updateInterview,
  scoreCandidateAI, getCandidateScore,
  type Candidate, type PipelineStage, type ScoringResult,
} from "@/api/recruitment";
import { recruitmentAiPalette } from "./recruitmentUtils";
import { CandidateSlideOverAiSection } from "./CandidateSlideOverAiSection";
import { CandidateSlideOverScrollBody } from "./CandidateSlideOverScrollBody";

export function CandidateSlideOver({
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
  onDeleted,
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
  onDeleted: () => void;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const cvFileInputRef = useRef<HTMLInputElement>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
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
    setDeleteConfirmOpen(false);
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

  const deleteCandidateMutation = useMutation({
    mutationFn: () => deleteCandidate(candidateId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recruitment", "candidates"] });
      setDeleteConfirmOpen(false);
      toast({ title: "Candidat supprimé" });
      onDeleted();
    },
    onError: (err: unknown) => {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? "Impossible de supprimer ce candidat.";
      toast({ title: "Erreur", description: String(message), variant: "destructive" });
    },
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
  const stageType = (currentStage?.stage_type ?? candidate.current_stage_type ?? "").toLowerCase();
  const isHiredCandidate = stageType === "hired";
  const isRejectedCandidate = stageType === "rejected";
  const isTerminalCandidate = isHiredCandidate || isRejectedCandidate;
  const stageBadgeLabel =
    currentStage?.name
    ?? (isHiredCandidate ? "Recruté" : isRejectedCandidate ? "Refusé" : null);
  const favorableCount = opinions.filter((o) => o.rating === "favorable").length;
  const defavorableCount = opinions.filter((o) => o.rating === "defavorable").length;

  const showRhActions = isRh && !isTerminalCandidate;
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
              {stageBadgeLabel ? (
                <Badge
                  variant={isRejectedCandidate ? "destructive" : isHiredCandidate ? "default" : "secondary"}
                  className="mt-2"
                >
                  {stageBadgeLabel}
                </Badge>
              ) : null}
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

          {isRh ? (
            <div
              className={cn(
                "flex flex-wrap gap-2 items-center",
                showRhActions && "pt-1 border-t border-border/60",
              )}
              aria-label="Suppression du candidat"
            >
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-9 text-xs border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive shrink-0"
                onClick={() => setDeleteConfirmOpen(true)}
              >
                <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                Supprimer le candidat
              </Button>
              {isTerminalCandidate ? (
                <p className="text-xs text-muted-foreground min-w-[12rem] flex-1">
                  {isHiredCandidate
                    ? "Retire ce candidat du recrutement. Le salarié créé reste dans l’effectif."
                    : "Retire ce candidat refusé du module recrutement."}
                </p>
              ) : null}
            </div>
          ) : null}

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

        <CandidateSlideOverAiSection
          candidate={candidate}
          isRh={isRh}
          companyId={companyId}
          scoringDetail={scoringDetail}
          scoringDetailLoading={scoringDetailLoading}
          scoringScoreDisplayed={scoringScoreDisplayed}
          scoringPal={scoringPal}
          scoreAiMutation={scoreAiMutation}
        />

        <CandidateSlideOverScrollBody
          candidate={candidate}
          candidateId={candidateId}
          companyId={companyId}
          isRh={isRh}
          notes={notes}
          loadingNotes={loadingNotes}
          noteText={noteText}
          setNoteText={setNoteText}
          noteAudioUrl={noteAudioUrl}
          setNoteAudioUrl={setNoteAudioUrl}
          addNoteMutation={addNoteMutation}
          interviews={interviews}
          loadingInterviews={loadingInterviews}
          interviewEditingId={interviewEditingId}
          setInterviewEditingId={setInterviewEditingId}
          interviewSummaryDraft={interviewSummaryDraft}
          setInterviewSummaryDraft={setInterviewSummaryDraft}
          updateInterviewSummaryMutation={updateInterviewSummaryMutation}
          onScheduleInterview={onScheduleInterview}
          timeline={timeline}
          loadingTimeline={loadingTimeline}
          uploadCvMutation={uploadCvMutation}
          cvFileInputRef={cvFileInputRef}
        />
      </SheetContent>

      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ce candidat ?</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2 text-sm text-muted-foreground">
                <p>
                  Vous allez supprimer définitivement{" "}
                  <span className="font-medium text-foreground">
                    {candidate.first_name} {candidate.last_name}
                  </span>
                  {" "}du module recrutement (historique, notes, entretiens).
                </p>
                {isHiredCandidate ? (
                  <p>
                    Le salarié associé dans l&apos;effectif ne sera pas supprimé.
                  </p>
                ) : null}
                {isRejectedCandidate ? (
                  <p>Ce candidat est actuellement en statut refusé.</p>
                ) : null}
                <p className="font-medium text-foreground">Cette action est irréversible.</p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteCandidateMutation.isPending}>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteCandidateMutation.isPending}
              onClick={(e) => {
                e.preventDefault();
                deleteCandidateMutation.mutate();
              }}
            >
              {deleteCandidateMutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : null}
              Supprimer définitivement
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Sheet>
  );
}

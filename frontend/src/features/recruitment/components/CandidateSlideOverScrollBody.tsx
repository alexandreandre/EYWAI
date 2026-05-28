import type { RefObject } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Plus, Calendar, Clock, MapPin, Link2, FileText, Loader2,
} from "lucide-react";
import type { UseMutationResult } from "@tanstack/react-query";
import type { Candidate, Note, Interview, TimelineEvent } from "@/api/recruitment";
import { CandidateNoteAudioRecorder } from "./CandidateNoteAudioRecorder";

export function CandidateSlideOverScrollBody({
  candidate,
  candidateId,
  companyId,
  isRh,
  notes,
  loadingNotes,
  noteText,
  setNoteText,
  noteAudioUrl,
  setNoteAudioUrl,
  addNoteMutation,
  interviews,
  loadingInterviews,
  interviewEditingId,
  setInterviewEditingId,
  interviewSummaryDraft,
  setInterviewSummaryDraft,
  updateInterviewSummaryMutation,
  onScheduleInterview,
  timeline,
  loadingTimeline,
  uploadCvMutation,
  cvFileInputRef,
}: {
  candidate: Candidate;
  candidateId: string | undefined;
  companyId: string;
  isRh: boolean;
  notes: Note[];
  loadingNotes: boolean;
  noteText: string;
  setNoteText: (v: string) => void;
  noteAudioUrl: string | null;
  setNoteAudioUrl: (v: string | null) => void;
  addNoteMutation: UseMutationResult<unknown, unknown, { content: string; audio_url?: string | null }, unknown>;
  interviews: Interview[];
  loadingInterviews: boolean;
  interviewEditingId: string | null;
  setInterviewEditingId: (v: string | null) => void;
  interviewSummaryDraft: string;
  setInterviewSummaryDraft: (v: string) => void;
  updateInterviewSummaryMutation: UseMutationResult<unknown, unknown, { interviewId: string; summary: string }, unknown>;
  onScheduleInterview: () => void;
  timeline: TimelineEvent[];
  loadingTimeline: boolean;
  uploadCvMutation: UseMutationResult<{ cv_url: string }, unknown, File, unknown>;
  cvFileInputRef: RefObject<HTMLInputElement | null>;
}) {
  return (
    <>
      {/* Bloc C — Consultation (scroll) : dossier → notes → entretiens → activité */}
      <ScrollArea className="flex-1 min-h-0">
              <div className="px-6 py-4 space-y-8 pb-10">
                <section aria-labelledby="candidate-section-dossier" className="space-y-5">
                  <h3 id="candidate-section-dossier" className="text-sm font-semibold">
                    Dossier candidat
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
                  <p className="text-[11px] text-muted-foreground/80 leading-snug">
                    Autres pièces (identité, diplômes…) : dépôt multi-fichiers prévu ultérieurement.
                  </p>
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
    </>
  );
}

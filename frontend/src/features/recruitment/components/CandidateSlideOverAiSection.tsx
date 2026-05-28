import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Loader2, RefreshCw, Sparkles, CheckCircle2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Candidate, ScoringResult } from "@/api/recruitment";
import { recruitmentAiPalette } from "./recruitmentUtils";

export function CandidateSlideOverAiSection({
  candidate,
  isRh,
  companyId,
  scoringDetail,
  scoringDetailLoading,
  scoringScoreDisplayed,
  scoringPal,
  scoreAiMutation,
}: {
  candidate: Candidate;
  isRh: boolean;
  companyId: string;
  scoringDetail: ScoringResult | undefined;
  scoringDetailLoading: boolean;
  scoringScoreDisplayed: number | null;
  scoringPal: ReturnType<typeof recruitmentAiPalette> | null;
  scoreAiMutation: { isPending: boolean; mutate: () => void };
}) {
  if (!((isRh && companyId) || candidate.ai_score != null)) return null;

  return (
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
  );
}

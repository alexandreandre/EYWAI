import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Plus, Briefcase } from "lucide-react";
import { cn } from "@/lib/utils";
import { isRecruitmentPriorityCandidate } from "@/api/recruitment";
import {
  recruitmentAiPalette,
  unifiedStageKeyForCandidate,
} from "@/features/recruitment/components/recruitmentUtils";
import { RecruitmentPipelineKpis } from "@/features/recruitment/components/RecruitmentPipelineKpis";
import { RecruitmentAnalyticsSection } from "@/features/recruitment/components/RecruitmentAnalyticsSection";
import { KanbanColumn } from "@/features/recruitment/components/KanbanColumn";
import { PipelineStageSummaryRow } from "@/features/recruitment/components/PipelineStageSummaryRow";
import type { RecruitmentPageModel } from "@/features/recruitment/hooks/useRecruitmentPageModel";

type Props = Pick<
  RecruitmentPageModel,
  | "companyId"
  | "isRh"
  | "mainSection"
  | "viewMode"
  | "jobFilterId"
  | "jobs"
  | "candidates"
  | "canShowPipeline"
  | "loadingJobStages"
  | "loadingCandidates"
  | "setShowCreateJob"
  | "sortedPipelineStages"
  | "standardStages"
  | "terminalStages"
  | "kanbanCompactLayout"
  | "candidatesByStage"
  | "jobTitlesByJobId"
  | "filteredCandidates"
  | "stages"
  | "handleCardClick"
  | "handleDrop"
>;

export function RecruitmentPipelineSection({
  companyId,
  isRh,
  mainSection,
  viewMode,
  jobFilterId,
  jobs,
  candidates,
  canShowPipeline,
  loadingJobStages,
  loadingCandidates,
  setShowCreateJob,
  sortedPipelineStages,
  standardStages,
  terminalStages,
  kanbanCompactLayout,
  candidatesByStage,
  jobTitlesByJobId,
  filteredCandidates,
  stages,
  handleCardClick,
  handleDrop,
}: Props) {
  const showKpis =
    mainSection === "pipeline" && canShowPipeline && !loadingJobStages && !loadingCandidates;

  return (
    <>
      {showKpis ? <RecruitmentPipelineKpis candidates={candidates} /> : null}

      {mainSection === "analytics" && isRh ? (
        <RecruitmentAnalyticsSection
          companyId={companyId}
          jobs={jobs}
          initialJobId={jobFilterId !== "__all__" ? jobFilterId : undefined}
        />
      ) : !canShowPipeline ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <Briefcase className="h-12 w-12 text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-medium mb-1">Aucun poste</h3>
            <p className="text-muted-foreground text-sm mb-4">
              Créez un poste pour commencer à recruter.
            </p>
            {isRh && (
              <Button onClick={() => setShowCreateJob(true)}>
                <Plus className="h-4 w-4 mr-2" /> Créer un poste
              </Button>
            )}
          </CardContent>
        </Card>
      ) : loadingJobStages || loadingCandidates ? (
        <div className="flex w-full min-w-0 gap-2 rounded-lg bg-muted/30 p-2 pb-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-80 min-h-0 min-w-0 flex-1 basis-0" />
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
              "flex w-full min-w-0 items-stretch rounded-lg bg-muted/30",
              kanbanCompactLayout ? "gap-2 p-2 pb-3" : "gap-4 p-2 pb-4",
            )}
          >
            {standardStages.map((stage) => (
              <div
                key={stage.id}
                id={`recruitment-pipeline-stage-${stage.id}`}
                className="min-w-0 flex-1"
              >
                <KanbanColumn
                  stage={stage}
                  candidates={candidatesByStage[stage.id] || []}
                  onCardClick={handleCardClick}
                  onCandidateDrop={handleDrop}
                  isRh={isRh}
                  compact={kanbanCompactLayout}
                  jobTitlesByJobId={jobTitlesByJobId}
                />
              </div>
            ))}
            {terminalStages.length > 0 && (
              <div
                className={cn(
                  "flex min-h-0 min-w-0 flex-1 flex-col border-l border-border pl-2",
                  kanbanCompactLayout ? "gap-2" : "gap-3",
                )}
              >
                {terminalStages.map((stage) => (
                  <div
                    key={stage.id}
                    className="flex min-h-0 min-w-0 flex-1 flex-col"
                    id={`recruitment-pipeline-stage-${stage.id}`}
                  >
                    <KanbanColumn
                      stage={stage}
                      candidates={candidatesByStage[stage.id] || []}
                      onCardClick={handleCardClick}
                      onCandidateDrop={handleDrop}
                      isRh={isRh}
                      compact={kanbanCompactLayout}
                      jobTitlesByJobId={jobTitlesByJobId}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : (
        <Card>
          <div className="w-full overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Candidat</TableHead>
                  <TableHead>Poste</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Téléphone</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Étape</TableHead>
                  <TableHead>Score IA</TableHead>
                  <TableHead>Date</TableHead>
                  {isRh && <TableHead className="text-right">Actions</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredCandidates.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={isRh ? 9 : 8}
                      className="text-center py-8 text-muted-foreground"
                    >
                      {candidates.length === 0
                        ? "Aucun candidat. Ajoutez un candidat pour démarrer."
                        : "Aucun candidat ne correspond aux filtres."}
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredCandidates.map((c) => {
                    const aiPal =
                      c.ai_score != null ? recruitmentAiPalette(c.ai_score) : null;
                    return (
                      <TableRow
                        key={c.id}
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => handleCardClick(c)}
                      >
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Avatar className="h-7 w-7">
                              <AvatarFallback className="text-xs bg-primary/10 text-primary">
                                {c.first_name[0]}
                                {c.last_name[0]}
                              </AvatarFallback>
                            </Avatar>
                            <span className="font-medium text-sm">
                              {c.first_name} {c.last_name}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell
                          className="text-sm max-w-[10rem] truncate"
                          title={jobTitlesByJobId[c.job_id]}
                        >
                          {jobTitlesByJobId[c.job_id] || "—"}
                        </TableCell>
                        <TableCell className="text-sm">{c.email || "—"}</TableCell>
                        <TableCell className="text-sm">{c.phone || "—"}</TableCell>
                        <TableCell className="text-sm">{c.source || "—"}</TableCell>
                        <TableCell>
                          <div className="flex flex-wrap items-center gap-1">
                            <Badge
                              variant={
                                c.current_stage_type === "rejected"
                                  ? "destructive"
                                  : c.current_stage_type === "hired"
                                    ? "default"
                                    : "secondary"
                              }
                              className="text-xs"
                            >
                              {c.current_stage_name || "—"}
                            </Badge>
                            {isRecruitmentPriorityCandidate(c) ? (
                              <Badge
                                variant="outline"
                                className="text-[9px] h-4 border-amber-400 text-amber-800"
                              >
                                RH
                              </Badge>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell>
                          {c.ai_score != null && aiPal ? (
                            <Badge
                              className={cn(
                                "text-[10px] font-bold tabular-nums border",
                                aiPal.badge,
                              )}
                            >
                              {c.ai_score}
                            </Badge>
                          ) : (
                            <span className="text-sm text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {new Date(c.created_at).toLocaleDateString("fr-FR")}
                        </TableCell>
                        {isRh && (
                          <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                            <Select onValueChange={(stageId) => handleDrop(c.id, stageId)}>
                              <SelectTrigger className="w-[140px] h-7 text-xs">
                                <SelectValue placeholder="Déplacer..." />
                              </SelectTrigger>
                              <SelectContent>
                                {stages
                                  .filter((s) => unifiedStageKeyForCandidate(c) !== s.id)
                                  .map((s) => (
                                    <SelectItem key={s.id} value={s.id} textValue={s.name}>
                                      {s.name}
                                    </SelectItem>
                                  ))}
                              </SelectContent>
                            </Select>
                          </TableCell>
                        )}
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>
        </Card>
      )}
    </>
  );
}

// frontend/src/pages/rh/Recruitment.tsx
// Page RH : Module Recrutement (ATS) — Pipeline Kanban + Vue Liste + Fiche candidat

import { RhPageHeader } from "@/components/layout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, Briefcase, RefreshCw } from "lucide-react";
import { recruitmentApiErrorMessage } from "@/features/recruitment/components/recruitmentUtils";
import { CandidateSlideOver } from "@/features/recruitment/components/CandidateSlideOver";
import { RecruitmentPageToolbar } from "@/features/recruitment/components/RecruitmentPageToolbar";
import { RecruitmentPipelineSection } from "@/features/recruitment/components/RecruitmentPipelineSection";
import { RecruitmentPageModals } from "@/features/recruitment/components/RecruitmentPageModals";
import { useRecruitmentPageModel } from "@/features/recruitment/hooks/useRecruitmentPageModel";

export function RecruitmentPage() {
  const model = useRecruitmentPageModel();

  const recruitmentPageHeader = (
    <RhPageHeader
      title="Recrutement"
      description={model.canLoadRecruitmentData ? model.pageSubtitle : undefined}
      actions={
        model.isRh && model.canLoadRecruitmentData ? (
          <Button onClick={() => model.setShowCreateJob(true)} className="shrink-0">
            <Plus className="h-4 w-4 mr-2" /> Nouveau poste
          </Button>
        ) : null
      }
    />
  );

  if (!model.companyId) {
    return (
      <div className="space-y-4">
        {recruitmentPageHeader}
        <div className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">
          Sélectionnez une entreprise pour accéder au module Recrutement.
        </div>
      </div>
    );
  }

  if (model.loadingSettings) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="flex gap-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-96 w-64" />
          ))}
        </div>
      </div>
    );
  }

  if (model.settingsError) {
    return (
      <div className="space-y-4">
        {recruitmentPageHeader}
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {recruitmentApiErrorMessage(model.settingsQueryError)}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-4 gap-2"
            onClick={() => void model.refetchSettings()}
          >
            <RefreshCw className="h-4 w-4" />
            Réessayer
          </Button>
        </div>
      </div>
    );
  }

  if (!model.recruitmentEnabled) {
    return (
      <div className="space-y-4">
        {recruitmentPageHeader}
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <Briefcase className="h-12 w-12 text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-medium mb-1">Module Recrutement désactivé</h3>
            <p className="text-muted-foreground text-sm max-w-md">
              Le module Recrutement n&apos;est pas activé pour cette entreprise. Contactez votre
              administrateur pour l&apos;activer dans les paramètres.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (model.loadingJobs) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="flex gap-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-96 w-64" />
          ))}
        </div>
      </div>
    );
  }

  if (model.jobsError) {
    return (
      <div className="space-y-4">
        {recruitmentPageHeader}
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {recruitmentApiErrorMessage(model.jobsQueryError)}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-4 gap-2"
            onClick={() => void model.refetchJobs()}
          >
            <RefreshCw className="h-4 w-4" />
            Réessayer
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {recruitmentPageHeader}

      <RecruitmentPageToolbar
        isRh={model.isRh}
        canShowPipeline={model.canShowPipeline}
        mainSection={model.mainSection}
        setMainSection={model.setMainSection}
        viewMode={model.viewMode}
        setViewMode={model.setViewMode}
        searchInput={model.searchInput}
        setSearchInput={model.setSearchInput}
        jobs={model.jobs}
        jobFilterId={model.jobFilterId}
        setJobFilterId={model.setJobFilterId}
        stages={model.stages}
        stageFilterId={model.stageFilterId}
        setStageFilterId={model.setStageFilterId}
        activeJobs={model.activeJobs}
        setShowCreateCandidate={model.setShowCreateCandidate}
      />

      <RecruitmentPipelineSection
        companyId={model.companyId}
        isRh={model.isRh}
        mainSection={model.mainSection}
        viewMode={model.viewMode}
        jobFilterId={model.jobFilterId}
        jobs={model.jobs}
        candidates={model.candidates}
        canShowPipeline={model.canShowPipeline}
        loadingJobStages={model.loadingJobStages}
        loadingCandidates={model.loadingCandidates}
        setShowCreateJob={model.setShowCreateJob}
        sortedPipelineStages={model.sortedPipelineStages}
        standardStages={model.standardStages}
        terminalStages={model.terminalStages}
        kanbanCompactLayout={model.kanbanCompactLayout}
        candidatesByStage={model.candidatesByStage}
        jobTitlesByJobId={model.jobTitlesByJobId}
        filteredCandidates={model.filteredCandidates}
        stages={model.stages}
        handleCardClick={model.handleCardClick}
        handleDrop={model.handleDrop}
      />

      <CandidateSlideOver
        candidate={model.selectedCandidate}
        open={model.slideOverOpen}
        onClose={model.closeSlideOver}
        isRh={model.isRh}
        stages={model.slideOverStages}
        onMove={model.handleMoveFromSlideOver}
        onHire={model.handleHireFromSlideOver}
        onRequestReject={model.handleRequestReject}
        onScheduleInterview={() => model.setShowInterviewModal(true)}
        companyId={model.companyId}
        onCandidateRefresh={(c) => model.setSelectedCandidate(c)}
        onDeleted={model.closeSlideOver}
      />

      <RecruitmentPageModals
        navigate={model.navigate}
        showCreateJob={model.showCreateJob}
        setShowCreateJob={model.setShowCreateJob}
        newJob={model.newJob}
        setNewJob={model.setNewJob}
        createJobMutation={model.createJobMutation}
        showEditJob={model.showEditJob}
        setShowEditJob={model.setShowEditJob}
        editJobTargetId={model.editJobTargetId}
        editJob={model.editJob}
        setEditJob={model.setEditJob}
        updateJobMutation={model.updateJobMutation}
        showCreateCandidate={model.showCreateCandidate}
        setShowCreateCandidate={model.setShowCreateCandidate}
        newCandidateJobId={model.newCandidateJobId}
        setNewCandidateJobId={model.setNewCandidateJobId}
        activeJobs={model.activeJobs}
        newCandidate={model.newCandidate}
        setNewCandidate={model.setNewCandidate}
        createCandidateMutation={model.createCandidateMutation}
        showRejectModal={model.showRejectModal}
        setShowRejectModal={model.setShowRejectModal}
        rejectReason={model.rejectReason}
        setRejectReason={model.setRejectReason}
        rejectDetail={model.rejectDetail}
        setRejectDetail={model.setRejectDetail}
        rejectionReasons={model.rejectionReasons}
        rejectCandidateId={model.rejectCandidateId}
        rejectStageId={model.rejectStageId}
        setRejectCandidateId={model.setRejectCandidateId}
        setRejectStageId={model.setRejectStageId}
        moveCandidateMutation={model.moveCandidateMutation}
        showHireModal={model.showHireModal}
        setShowHireModal={model.setShowHireModal}
        hireData={model.hireData}
        setHireData={model.setHireData}
        hireJobTitle={model.hireJobTitle}
        hireCandidateId={model.hireCandidateId}
        setHireCandidateId={model.setHireCandidateId}
        servicesQuery={model.servicesQuery}
        hireMutation={model.hireMutation}
        hireSuccessInfo={model.hireSuccessInfo}
        setHireSuccessInfo={model.setHireSuccessInfo}
        showDuplicateEmployeeModal={model.showDuplicateEmployeeModal}
        setShowDuplicateEmployeeModal={model.setShowDuplicateEmployeeModal}
        duplicateEmployeeInfo={model.duplicateEmployeeInfo}
        setDuplicateEmployeeInfo={model.setDuplicateEmployeeInfo}
        showInterviewModal={model.showInterviewModal}
        setShowInterviewModal={model.setShowInterviewModal}
        interviewData={model.interviewData}
        setInterviewData={model.setInterviewData}
        interviewParticipantIds={model.interviewParticipantIds}
        setInterviewParticipantIds={model.setInterviewParticipantIds}
        interviewCompanyUsers={model.interviewCompanyUsers}
        loadingInterviewCompanyUsers={model.loadingInterviewCompanyUsers}
        createInterviewMutation={model.createInterviewMutation}
      />
    </div>
  );
}

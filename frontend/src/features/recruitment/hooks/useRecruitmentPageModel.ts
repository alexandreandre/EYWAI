import { useState, useMemo, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient, useQueries } from "@tanstack/react-query";
import {
  getRecruitmentSettings,
  getJobs,
  createJob,
  updateJob,
  getPipelineStages,
  getCandidates,
  createCandidate,
  moveCandidate,
  createInterview,
  hireCandidate,
  getRejectionReasons,
  checkDuplicate,
  countActionableCandidates,
  type Job,
  type PipelineStage,
  type Candidate,
  type HireResult,
} from "@/api/recruitment";
import apiClient from "@/api/apiClient";
import { listCompanyServices } from "@/api/objectives";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";
import { useToast } from "@/components/ui/use-toast";
import {
  SEARCH_DEBOUNCE_MS,
  buildUnifiedPipelineStages,
  unifiedStageKeyForCandidate,
  resolveStageIdForCandidate,
} from "@/features/recruitment/components/recruitmentUtils";
import {
  EMPTY_EMPLOYEE_CONTRACT_CONFIG,
  normalizeContractType,
  type EmployeeContractConfigValues,
} from "@/constants/contracts";

type HireFormData = {
  hire_date: string;
  job_title: string;
  site: string;
  service_id: string;
} & EmployeeContractConfigValues;

function createInitialHireData(overrides?: Partial<HireFormData>): HireFormData {
  return {
    hire_date: "",
    job_title: "",
    site: "",
    service_id: "",
    ...EMPTY_EMPLOYEE_CONTRACT_CONFIG,
    ...overrides,
  };
}

export function useRecruitmentPageModel() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? "";
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [mainSection, setMainSection] = useState<"pipeline" | "analytics">("pipeline");
  const [viewMode, setViewMode] = useState<"kanban" | "list">("kanban");
  const [jobFilterId, setJobFilterId] = useState<string>("__all__");
  const [newCandidateJobId, setNewCandidateJobId] = useState<string>("");
  const [editJobTargetId, setEditJobTargetId] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [searchText, setSearchText] = useState("");
  const [stageFilterId, setStageFilterId] = useState<string>("__all__");
  const [showEditJob, setShowEditJob] = useState(false);
  const [editJob, setEditJob] = useState({
    title: "",
    description: "",
    location: "",
    contract_type: "CDI",
    status: "active" as Job["status"],
  });
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
    id: string;
    first_name: string;
    last_name: string;
    email: string;
  } | null>(null);
  const [hireSuccessInfo, setHireSuccessInfo] = useState<{
    employeeId: string;
    username?: string;
    email?: string;
    generatedPassword?: string;
  } | null>(null);

  const [newJob, setNewJob] = useState({
    title: "",
    description: "",
    location: "",
    contract_type: "CDI",
    status: "active",
  });
  const [newCandidate, setNewCandidate] = useState({
    first_name: "",
    last_name: "",
    email: "",
    phone: "",
    source: "",
  });
  const [hireData, setHireData] = useState<HireFormData>(() => createInitialHireData());
  const [rejectReason, setRejectReason] = useState("");
  const [rejectDetail, setRejectDetail] = useState("");
  const [interviewData, setInterviewData] = useState({
    interview_type: "Entretien RH",
    scheduled_at: "",
    duration_minutes: 60,
    location: "",
    meeting_link: "",
  });
  const [interviewParticipantIds, setInterviewParticipantIds] = useState<string[]>([]);

  const isRh = user?.role === "rh" || user?.role === "admin" || user?.role === "collaborateur_rh";

  useEffect(() => {
    const t = window.setTimeout(() => setSearchText(searchInput.trim()), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(t);
  }, [searchInput]);

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

  const {
    data: settings,
    isLoading: loadingSettings,
    isError: settingsError,
    error: settingsQueryError,
    refetch: refetchSettings,
  } = useQuery({
    queryKey: ["recruitment", "settings", companyId],
    queryFn: getRecruitmentSettings,
    enabled: Boolean(companyId),
  });

  const recruitmentEnabled = settings?.enabled === true;
  const canLoadRecruitmentData = Boolean(companyId) && recruitmentEnabled;

  const {
    data: jobs = [],
    isLoading: loadingJobs,
    isError: jobsError,
    error: jobsQueryError,
    refetch: refetchJobs,
  } = useQuery({
    queryKey: ["recruitment", "jobs", companyId],
    queryFn: () => getJobs(),
    enabled: canLoadRecruitmentData,
  });

  const activeJobs = jobs.filter((j) => j.status === "active");

  const jobTitlesByJobId = useMemo(
    () => Object.fromEntries(jobs.map((j) => [j.id, j.title])),
    [jobs],
  );

  const stageQueries = useQueries({
    queries: jobs.map((job) => ({
      queryKey: ["recruitment", "stages", job.id],
      queryFn: () => getPipelineStages(job.id),
      enabled: Boolean(job.id) && canLoadRecruitmentData,
    })),
  });

  const stagesByJobId = useMemo(() => {
    const map: Record<string, PipelineStage[]> = {};
    jobs.forEach((job, index) => {
      map[job.id] = stageQueries[index]?.data ?? [];
    });
    return map;
  }, [jobs, stageQueries]);

  const loadingJobStages = stageQueries.some((q) => q.isLoading);

  const stages = useMemo(() => buildUnifiedPipelineStages(), []);

  const { data: candidates = [], isLoading: loadingCandidates } = useQuery({
    queryKey: ["recruitment", "candidates", "all", searchText, companyId],
    queryFn: () => getCandidates({ search: searchText || undefined }),
    enabled: canLoadRecruitmentData,
  });

  useEffect(() => {
    if (newCandidateJobId) return;
    if (activeJobs.length > 0) setNewCandidateJobId(activeJobs[0].id);
  }, [activeJobs, newCandidateJobId]);

  const { data: rejectionReasons } = useQuery({
    queryKey: ["recruitment", "rejection-reasons", companyId],
    queryFn: getRejectionReasons,
    enabled: canLoadRecruitmentData,
  });

  const createJobMutation = useMutation({
    mutationFn: () => createJob(newJob),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recruitment", "jobs"] });
      setShowCreateJob(false);
      setNewJob({ title: "", description: "", location: "", contract_type: "CDI", status: "active" });
      toast({ title: "Poste créé avec succès" });
    },
    onError: () =>
      toast({ title: "Erreur", description: "Impossible de créer le poste.", variant: "destructive" }),
  });

  const updateJobMutation = useMutation({
    mutationFn: () =>
      updateJob(editJobTargetId!, {
        title: editJob.title,
        description: editJob.description || undefined,
        location: editJob.location || undefined,
        contract_type: editJob.contract_type,
        status: editJob.status,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recruitment", "jobs"] });
      setShowEditJob(false);
      toast({ title: "Poste mis à jour" });
    },
    onError: () =>
      toast({ title: "Erreur", description: "Impossible de modifier le poste.", variant: "destructive" }),
  });

  const createCandidateMutation = useMutation({
    mutationFn: () => createCandidate({ job_id: newCandidateJobId, ...newCandidate }),
    onSuccess: async (newCand) => {
      queryClient.invalidateQueries({ queryKey: ["recruitment", "candidates"] });
      setShowCreateCandidate(false);
      setNewCandidate({ first_name: "", last_name: "", email: "", phone: "", source: "" });
      toast({ title: "Candidat ajouté" });
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
    onError: () =>
      toast({ title: "Erreur", description: "Impossible de créer le candidat.", variant: "destructive" }),
  });

  const candidatesKey = ["recruitment", "candidates", "all", searchText];

  const moveCandidateMutation = useMutation({
    mutationFn: ({
      candidateId,
      stageId,
      reason,
      detail,
    }: {
      candidateId: string;
      stageId: string;
      reason?: string;
      detail?: string;
    }) =>
      moveCandidate(candidateId, {
        stage_id: stageId,
        rejection_reason: reason,
        rejection_reason_detail: detail,
      }),
    onMutate: async ({ candidateId, stageId }) => {
      await queryClient.cancelQueries({ queryKey: candidatesKey });
      const prev = queryClient.getQueryData<Candidate[]>(candidatesKey);
      const candidate = prev?.find((c) => c.id === candidateId);
      const targetStage = candidate
        ? (stagesByJobId[candidate.job_id] ?? []).find((s) => s.id === stageId)
        : undefined;
      if (prev) {
        queryClient.setQueryData<Candidate[]>(
          candidatesKey,
          prev.map((c) =>
            c.id === candidateId
              ? {
                  ...c,
                  current_stage_id: stageId,
                  current_stage_name: targetStage?.name ?? c.current_stage_name,
                  current_stage_type: targetStage?.stage_type ?? c.current_stage_type,
                }
              : c,
          ),
        );
      }
      return { prev };
    },
    onError: (err: { response?: { data?: { detail?: string } } }, _vars, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(candidatesKey, ctx.prev);
      toast({
        title: "Erreur",
        description: err?.response?.data?.detail || "Impossible de déplacer le candidat.",
        variant: "destructive",
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: candidatesKey });
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
        statut: data.statut,
        contract_end_date: data.contract_end_date?.trim() || undefined,
        date_debut_execution: data.date_debut_execution?.trim() || undefined,
        date_conclusion_contrat: data.date_conclusion_contrat?.trim() || undefined,
        maintien_regime_apprenti: Boolean(data.maintien_regime_apprenti),
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
      setHireData(createInitialHireData());
      toast({ title: "Embauche finalisée", description: res.message });
      if (res.employee_id) {
        setHireSuccessInfo({
          employeeId: res.employee_id,
          username: res.username,
          email: res.email,
          generatedPassword: res.generated_password,
        });
      }
    },
    onError: (err: { response?: { data?: { detail?: string } } }) => {
      toast({
        title: "Erreur",
        description: err?.response?.data?.detail || "Impossible de finaliser l'embauche.",
        variant: "destructive",
      });
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
      setInterviewData({
        interview_type: "Entretien RH",
        scheduled_at: "",
        duration_minutes: 60,
        location: "",
        meeting_link: "",
      });
      setInterviewParticipantIds([]);
      toast({ title: "Entretien planifié" });
    },
    onError: () =>
      toast({ title: "Erreur", description: "Impossible de planifier l'entretien.", variant: "destructive" }),
  });

  const sortedPipelineStages = useMemo(
    () => [...stages].sort((a, b) => a.position - b.position),
    [stages],
  );
  const standardStages = useMemo(
    () => sortedPipelineStages.filter((s) => s.stage_type === "standard"),
    [sortedPipelineStages],
  );
  const terminalStages = useMemo(() => {
    const hired = sortedPipelineStages.find((s) => s.stage_type === "hired");
    const rejected = sortedPipelineStages.find((s) => s.stage_type === "rejected");
    return [hired, rejected].filter(Boolean) as PipelineStage[];
  }, [sortedPipelineStages]);

  const kanbanHorizontalSlots = standardStages.length + (terminalStages.length > 0 ? 1 : 0);
  const kanbanCompactLayout = kanbanHorizontalSlots > 5;

  const filteredCandidates = useMemo(() => {
    let list = candidates;
    if (jobFilterId !== "__all__") {
      list = list.filter((c) => c.job_id === jobFilterId);
    }
    if (stageFilterId !== "__all__") {
      list = list.filter((c) => unifiedStageKeyForCandidate(c) === stageFilterId);
    }
    return list;
  }, [candidates, jobFilterId, stageFilterId]);

  const pipelineActionableCount = useMemo(
    () => countActionableCandidates(candidates),
    [candidates],
  );

  const pageSubtitle = useMemo(() => {
    const parts = [
      `${pipelineActionableCount} candidat${pipelineActionableCount !== 1 ? "s" : ""} en cours`,
      `${candidates.length} au total`,
      `${activeJobs.length} poste${activeJobs.length !== 1 ? "s" : ""} actif${activeJobs.length !== 1 ? "s" : ""}`,
    ];
    return parts.join(" · ");
  }, [pipelineActionableCount, candidates.length, activeJobs.length]);

  const openEditJobModal = useCallback(
    (jobId: string) => {
      const job = jobs.find((j) => j.id === jobId);
      if (!job) return;
      setEditJobTargetId(jobId);
      setEditJob({
        title: job.title,
        description: job.description ?? "",
        location: job.location ?? "",
        contract_type: job.contract_type ?? "CDI",
        status: job.status,
      });
      setShowEditJob(true);
    },
    [jobs],
  );

  const candidatesByStage = useMemo(() => {
    const map: Record<string, Candidate[]> = {};
    for (const s of stages) map[s.id] = [];
    const fallbackStageId =
      stages.find((s) => s.stage_type === "standard")?.id ?? stages[0]?.id;
    for (const c of filteredCandidates) {
      const key = unifiedStageKeyForCandidate(c);
      if (map[key]) {
        map[key].push(c);
      } else if (fallbackStageId) {
        map[fallbackStageId].push(c);
      }
    }
    return map;
  }, [stages, filteredCandidates]);

  const resolveDropStageId = useCallback(
    (candidateId: string, unifiedStageId: string): string | null => {
      const candidate = candidates.find((c) => c.id === candidateId);
      if (!candidate) return null;
      return resolveStageIdForCandidate(candidate, unifiedStageId, stagesByJobId);
    },
    [candidates, stagesByJobId],
  );

  const slideOverStages = useMemo(
    () => (selectedCandidate ? (stagesByJobId[selectedCandidate.job_id] ?? []) : []),
    [selectedCandidate, stagesByJobId],
  );

  const hireJobMeta = useMemo(() => {
    if (!hireCandidateId) return undefined;
    const cand = candidates.find((c) => c.id === hireCandidateId);
    if (!cand) return undefined;
    const job = jobs.find((j) => j.id === cand.job_id);
    return job
      ? {
          title: job.title,
          contract_type: normalizeContractType(job.contract_type),
          location: job.location ?? "",
        }
      : undefined;
  }, [hireCandidateId, candidates, jobs]);

  const hireJobTitle = hireJobMeta?.title;

  useEffect(() => {
    if (!hireCandidateId || !showHireModal) return;
    setHireData(
      createInitialHireData({
        job_title: hireJobMeta?.title ?? "",
        contract_type: hireJobMeta?.contract_type ?? EMPTY_EMPLOYEE_CONTRACT_CONFIG.contract_type,
        site: hireJobMeta?.location ?? "",
      }),
    );
  }, [hireCandidateId, showHireModal, hireJobMeta?.title, hireJobMeta?.contract_type, hireJobMeta?.location]);

  const canShowPipeline = jobs.length > 0 || candidates.length > 0;

  const handleCardClick = (c: Candidate) => {
    setSelectedCandidate(c);
    setSlideOverOpen(true);
  };

  const handleDrop = (candidateId: string, unifiedStageId: string) => {
    const stageId = resolveDropStageId(candidateId, unifiedStageId);
    if (!stageId) {
      toast({
        title: "Erreur",
        description: "Impossible de déplacer ce candidat : étape introuvable pour son poste.",
        variant: "destructive",
      });
      return;
    }
    const candidate = candidates.find((c) => c.id === candidateId);
    const stage = candidate
      ? (stagesByJobId[candidate.job_id] ?? []).find((s) => s.id === stageId)
      : undefined;
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
    const candidate = candidates.find((c) => c.id === candidateId);
    const stage = candidate
      ? (stagesByJobId[candidate.job_id] ?? []).find((s) => s.id === stageId)
      : undefined;
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

  const handleHireFromSlideOver = (candidateId: string) => {
    setHireCandidateId(candidateId);
    setShowHireModal(true);
  };

  const handleRequestReject = (candidateId: string) => {
    const candidate = candidates.find((c) => c.id === candidateId);
    if (!candidate) return;
    const rejectedStage = (stagesByJobId[candidate.job_id] ?? []).find(
      (s) => s.stage_type === "rejected",
    );
    if (rejectedStage) {
      setRejectCandidateId(candidateId);
      setRejectStageId(rejectedStage.id);
      setShowRejectModal(true);
    }
  };

  const closeSlideOver = () => {
    setSlideOverOpen(false);
    setSelectedCandidate(null);
  };

  return {
    navigate,
    companyId,
    isRh,
    canLoadRecruitmentData,
    recruitmentEnabled,
    loadingSettings,
    settingsError,
    settingsQueryError,
    refetchSettings,
    loadingJobs,
    jobsError,
    jobsQueryError,
    refetchJobs,
    mainSection,
    setMainSection,
    viewMode,
    setViewMode,
    jobFilterId,
    setJobFilterId,
    newCandidateJobId,
    setNewCandidateJobId,
    editJobTargetId,
    searchInput,
    setSearchInput,
    stageFilterId,
    setStageFilterId,
    showEditJob,
    setShowEditJob,
    editJob,
    setEditJob,
    selectedCandidate,
    setSelectedCandidate,
    slideOverOpen,
    setSlideOverOpen,
    showCreateJob,
    setShowCreateJob,
    showCreateCandidate,
    setShowCreateCandidate,
    showHireModal,
    setShowHireModal,
    showRejectModal,
    setShowRejectModal,
    showInterviewModal,
    setShowInterviewModal,
    deleteStageTarget,
    setDeleteStageTarget,
    showDuplicateEmployeeModal,
    setShowDuplicateEmployeeModal,
    hireCandidateId,
    setHireCandidateId,
    rejectCandidateId,
    setRejectCandidateId,
    rejectStageId,
    setRejectStageId,
    duplicateEmployeeInfo,
    setDuplicateEmployeeInfo,
    hireSuccessInfo,
    setHireSuccessInfo,
    newJob,
    setNewJob,
    newCandidate,
    setNewCandidate,
    hireData,
    setHireData,
    rejectReason,
    setRejectReason,
    rejectDetail,
    setRejectDetail,
    interviewData,
    setInterviewData,
    interviewParticipantIds,
    setInterviewParticipantIds,
    servicesQuery,
    interviewCompanyUsers,
    loadingInterviewCompanyUsers,
    jobs,
    activeJobs,
    jobTitlesByJobId,
    stagesByJobId,
    loadingJobStages,
    stages,
    candidates,
    loadingCandidates,
    rejectionReasons,
    createJobMutation,
    updateJobMutation,
    createCandidateMutation,
    moveCandidateMutation,
    hireMutation,
    createInterviewMutation,
    sortedPipelineStages,
    standardStages,
    terminalStages,
    kanbanCompactLayout,
    filteredCandidates,
    pageSubtitle,
    openEditJobModal,
    candidatesByStage,
    slideOverStages,
    hireJobTitle,
    canShowPipeline,
    handleCardClick,
    handleDrop,
    handleMoveFromSlideOver,
    handleHireFromSlideOver,
    handleRequestReject,
    closeSlideOver,
  };
}

export type RecruitmentPageModel = ReturnType<typeof useRecruitmentPageModel>;

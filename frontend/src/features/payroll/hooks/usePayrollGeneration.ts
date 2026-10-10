import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { generatePayslip } from '@/api/payslips';
import {
  getPayrollGenerationErrorMessage,
  PAYROLL_GENERATION_FALLBACK,
  sanitizeBackendMessage,
} from '@/lib/errorMessages';
import { queryKeys } from '@/lib/queryKeys';
import { invalidateExportsPageQueries } from '@/lib/exportsQuery';
import { toast } from '@/hooks/use-toast';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import {
  monthYearLabel,
  readAverageGenerationMs,
  recordGenerationDuration,
} from '@/features/payroll/utils/payrollMonth';
import {
  refusForcablesEnGroupe,
  extractGenerationRefusal,
  splitGenerationWarnings,
  type GenerationRefusalCode,
  type RefusalDetails,
} from '@/features/payroll/utils/generationGuards';
import type { JourEnConflit } from '@/features/payroll/utils/heuresSurArret';
import {
  clesApresAnnulation,
  clesAutourDesBulletins,
  invaliderCles,
} from '@/features/payroll/utils/invalidationsBulletin';
import {
  toastsDeFinDeRecalcul,
  type RecalculTermine,
  montantsDepuisReponse,
  type MontantsBulletin,
} from '@/features/payroll/utils/bulletinARecalculer';
import {
  lienQuitteLaPage,
  noterInterruption,
  phraseAnnulation,
  questionQuitterGeneration,
  recapitulatifEchecs,
  type EchecGeneration,
} from '@/features/payroll/utils/generationEnCours';

export type PayrollGenerationJob = {
  employeeId: string;
  employeeName: string;
  year: number;
  month: number;
  /** Reposte avec `force_calendrier_incomplet` (après refus 422 confirmé). */
  forceCalendrierIncomplet?: boolean;
  /** Reposte avec `regenerer_bulletin_valide` (après refus 409 confirmé). */
  regenererBulletinValide?: boolean;
  /** Montants lus sur la ligne avant le recalcul : le toast compare avant → après. */
  montantsAvant?: MontantsBulletin;
};

/** Job refusé par une garde backend (422 calendrier / 409 bulletin validé). */
export type PayrollGenerationRefusal = {
  job: PayrollGenerationJob;
  code: GenerationRefusalCode;
  message: string;
  /** Recopié du refus structuré (jours à saisir du 422 calendrier_incomplet). */
  details?: RefusalDetails;
  /** Jours où des heures sont saisies sur un arrêt (`heures_sur_jour_d_arret`). */
  jours?: JourEnConflit[];
};

export type PayrollGenerationLogEntry = {
  id: string;
  employeeId: string;
  employeeName: string;
  year: number;
  month: number;
  status: 'success' | 'warning' | 'error';
  error?: string;
  warnings?: string[];
  /** Points à arbitrer : le bulletin est bon, la RH a une décision à prendre. */
  infos?: string[];
};

export type PayrollGenerationPhase = 'idle' | 'running' | 'done';

const INTRA_CAP = 0.95;

function intraJobFraction(elapsedMs: number, estimatedMs: number): number {
  const raw = Math.min(1, elapsedMs / estimatedMs);
  return Math.min(INTRA_CAP, 1 - (1 - raw) ** 1.6);
}

export function payrollJobKey(
  job: Pick<PayrollGenerationJob, 'employeeId' | 'year' | 'month'>
): string {
  return `${job.employeeId}-${job.year}-${job.month}`;
}

/** sessionStorage, ou null quand le navigateur l'interdit. */
function stockageDeSession(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function isAbortError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === 'AbortError') return true;
  if (typeof error === 'object' && error !== null && 'code' in error) {
    return (error as { code?: string }).code === 'ERR_CANCELED';
  }
  return false;
}

export function usePayrollGeneration() {
  const companyId = useActiveCompanyId();
  const queryClient = useQueryClient();

  const [phase, setPhase] = useState<PayrollGenerationPhase>('idle');
  const [log, setLog] = useState<PayrollGenerationLogEntry[]>([]);
  const [currentJob, setCurrentJob] = useState<PayrollGenerationJob | null>(null);
  const [queuedJobs, setQueuedJobs] = useState<PayrollGenerationJob[]>([]);
  const [progress, setProgress] = useState(0);
  const [estimatedRemainingSec, setEstimatedRemainingSec] = useState<number | null>(null);
  const [totalJobs, setTotalJobs] = useState(0);
  const [failedJobs, setFailedJobs] = useState<Record<string, string>>({});
  const [refusedJobs, setRefusedJobs] = useState<PayrollGenerationRefusal[]>([]);
  /** Échecs de la dernière passe, gardés une fois le suivi fermé. */
  const [recapEchecs, setRecapEchecs] = useState<EchecGeneration[]>([]);
  /** Phrase laissée par la dernière annulation, jusqu'à la prochaine génération. */
  const [annulation, setAnnulation] = useState<string | null>(null);

  /** Arrêt demandé, le bulletin en cours se termine. */
  const [arretDemande, setArretDemande] = useState(false);

  const abortRef = useRef(false);
  const tickRef = useRef<number | null>(null);
  const dismissTimerRef = useRef<number | null>(null);
  const jobStartRef = useRef<number>(0);
  const completedCountRef = useRef(0);
  const totalRef = useRef(0);
  const estimatedMsRef = useRef(readAverageGenerationMs());
  const queueRef = useRef<PayrollGenerationJob[]>([]);
  const processingRef = useRef(false);
  // Recalculs terminés du tour en cours, annoncés ensemble à la fin.
  const recalculsRef = useRef<RecalculTermine[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);
  const logRef = useRef<PayrollGenerationLogEntry[]>([]);
  const companyIdRef = useRef(companyId);
  companyIdRef.current = companyId;

  const stopTick = useCallback(() => {
    if (tickRef.current != null) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }
  }, []);

  const clearDismissTimer = useCallback(() => {
    if (dismissTimerRef.current != null) {
      window.clearTimeout(dismissTimerRef.current);
      dismissTimerRef.current = null;
    }
  }, []);

  const invalidatePayslips = useCallback(
    async (employeeId: string) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.employeePayslips(companyId, employeeId),
      });
    },
    [companyId, queryClient]
  );

  // Une fois par lot et non par bulletin : le contrôle avant paie et les
  // anomalies portent sur tous les salariés du mois.
  const invalidateAroundPayslips = useCallback(() => {
    void invaliderCles(queryClient, clesAutourDesBulletins(companyId));
  }, [companyId, queryClient]);

  const updateProgress = useCallback((completed: number, intraFraction: number) => {
    const total = totalRef.current;
    if (total <= 0) {
      setProgress(0);
      return;
    }
    const value = ((completed + intraFraction) / total) * 100;
    setProgress(Math.min(99.5, value));
  }, []);

  const startTick = useCallback(() => {
    stopTick();
    tickRef.current = window.setInterval(() => {
      const elapsed = Date.now() - jobStartRef.current;
      const estimated = estimatedMsRef.current;
      const intra = intraJobFraction(elapsed, estimated);
      updateProgress(completedCountRef.current, intra);

      const jobsLeft = totalRef.current - completedCountRef.current;
      const currentRemaining = Math.max(0, estimated - elapsed);
      const futureJobs = Math.max(0, jobsLeft - 1);
      const totalRemainingMs = currentRemaining + futureJobs * estimated;
      setEstimatedRemainingSec(Math.ceil(totalRemainingMs / 1000));
    }, 80);
  }, [stopTick, updateProgress]);

  const processQueue = useCallback(async () => {
    if (processingRef.current) return;
    processingRef.current = true;
    let salarieInterrompu: string | null = null;

    try {
      while (queueRef.current.length > 0 && !abortRef.current) {
        const job = queueRef.current.shift()!;
        setQueuedJobs([...queueRef.current]);
        setCurrentJob(job);
        jobStartRef.current = Date.now();
        startTick();

        const controller = new AbortController();
        abortControllerRef.current = controller;

        let entry: PayrollGenerationLogEntry;
        let refusal: PayrollGenerationRefusal | null = null;
        // Un forçage ne reste jamais silencieux : annoncé en fin de tour.
        const avertissementsForces: { title: string; description: string }[] = [];
        try {
          const response = await generatePayslip(
            {
              employee_id: job.employeeId,
              year: job.year,
              month: job.month,
              ...(job.forceCalendrierIncomplet
                ? { force_calendrier_incomplet: true }
                : {}),
              ...(job.regenererBulletinValide
                ? { regenerer_bulletin_valide: true }
                : {}),
            },
            controller.signal,
            companyId
          );

          const duration = Date.now() - jobStartRef.current;
          recordGenerationDuration(duration);
          estimatedMsRef.current = readAverageGenerationMs();

          if (response.status === 'success') {
            const {
              messages: warnings,
              infos,
              guardWarnings,
            } = splitGenerationWarnings(response.warnings);
            for (const guardWarning of guardWarnings) {
              avertissementsForces.push({
                title: `${monthYearLabel(job.month, job.year)} — ${job.employeeName}`,
                description: guardWarning.message,
              });
            }
            entry = {
              id: payrollJobKey(job),
              employeeId: job.employeeId,
              employeeName: job.employeeName,
              year: job.year,
              month: job.month,
              status: warnings.length > 0 ? 'warning' : 'success',
              warnings,
              infos: infos.length > 0 ? infos : undefined,
              error: warnings.length > 0 ? warnings.join(' · ') : undefined,
            };
            if (job.montantsAvant) {
              // Annoncé en fin de tour : un seul message pour tout un lot.
              recalculsRef.current.push({
                employeeName: job.employeeName,
                avant: job.montantsAvant,
                apres: montantsDepuisReponse(response),
              });
            }
            setFailedJobs((prev) => {
              const next = { ...prev };
              delete next[payrollJobKey(job)];
              return next;
            });
          } else {
            const errorMessage =
              sanitizeBackendMessage(response.message) || PAYROLL_GENERATION_FALLBACK;
            entry = {
              id: payrollJobKey(job),
              employeeId: job.employeeId,
              employeeName: job.employeeName,
              year: job.year,
              month: job.month,
              status: 'error',
              error: errorMessage,
            };
            setFailedJobs((prev) => ({ ...prev, [payrollJobKey(job)]: errorMessage }));
          }
        } catch (error: unknown) {
          if (controller.signal.aborted || isAbortError(error)) {
            salarieInterrompu = job.employeeId;
            stopTick();
            break;
          }
          // Refus structuré d'une garde (422 calendrier / 409 bulletin validé) :
          // la boucle continue, le job est mémorisé pour un forçage explicite.
          const structuredRefusal = extractGenerationRefusal(error);
          if (structuredRefusal) {
            refusal = { job, ...structuredRefusal };
          }
          const errorMessage = structuredRefusal
            ? structuredRefusal.message
            : getPayrollGenerationErrorMessage(error);
          entry = {
            id: payrollJobKey(job),
            employeeId: job.employeeId,
            employeeName: job.employeeName,
            year: job.year,
            month: job.month,
            status: 'error',
            error: errorMessage,
          };
          setFailedJobs((prev) => ({ ...prev, [payrollJobKey(job)]: errorMessage }));
        } finally {
          abortControllerRef.current = null;
        }

        stopTick();

        // Remplace un éventuel refus antérieur du même job par l'issue du jour.
        setRefusedJobs((prev) => {
          const rest = prev.filter(
            (r) => payrollJobKey(r.job) !== payrollJobKey(job)
          );
          return refusal ? [...rest, refusal] : rest;
        });

        completedCountRef.current += 1;
        logRef.current = [...logRef.current, entry];
        setLog(logRef.current);
        updateProgress(completedCountRef.current, 0);
        await invalidatePayslips(job.employeeId);
        for (const avertissement of avertissementsForces) {
          toast({ variant: 'warning', duration: 15000, ...avertissement });
        }
        // Arrêt demandé pendant ce bulletin : il est allé au bout côté serveur,
        // il est compté et sa ligne a pris son état ; les suivants ne partent pas.
        if (abortRef.current) break;
      }
    } finally {
      stopTick();
      setCurrentJob(null);
      setArretDemande(false);
      processingRef.current = false;
      if (abortRef.current || queueRef.current.length === 0) {
        for (const message of toastsDeFinDeRecalcul(recalculsRef.current)) toast(message);
        recalculsRef.current = [];
      }

      if (abortRef.current) {
        queueRef.current = [];
        setQueuedJobs([]);
        abortRef.current = false;
        setPhase('idle');
        setEstimatedRemainingSec(null);
        const generes = logRef.current.filter((e) => e.status !== 'error').length;
        const phrase = phraseAnnulation(generes, totalRef.current, salarieInterrompu !== null);
        setAnnulation(phrase);
        toast({ title: 'Génération arrêtée', description: phrase });
        void invaliderCles(queryClient, clesApresAnnulation(companyId, salarieInterrompu));
      } else if (queueRef.current.length > 0) {
        void processQueue();
      } else {
        setProgress(100);
        setEstimatedRemainingSec(0);
        setPhase('done');
        invalidateAroundPayslips();
        invalidateExportsPageQueries(queryClient);
      }
    }
  }, [companyId, invalidateAroundPayslips, invalidatePayslips, queryClient, startTick, stopTick, updateProgress]);

  const enqueueJobs = useCallback(
    (jobs: PayrollGenerationJob[]) => {
      if (jobs.length === 0) return;

      const inFlightKeys = new Set<string>();
      if (currentJob) inFlightKeys.add(payrollJobKey(currentJob));
      for (const queued of queueRef.current) inFlightKeys.add(payrollJobKey(queued));

      const newJobs = jobs.filter((job) => !inFlightKeys.has(payrollJobKey(job)));
      if (newJobs.length === 0) return;

      const startingFresh = phase === 'idle' && !processingRef.current;
      if (startingFresh) {
        clearDismissTimer();
        logRef.current = [];
        setLog([]);
        setFailedJobs({});
        setRefusedJobs([]);
        setRecapEchecs([]);
        setAnnulation(null);
        completedCountRef.current = 0;
        totalRef.current = 0;
        setProgress(0);
        setEstimatedRemainingSec(null);
        estimatedMsRef.current = readAverageGenerationMs();
      }

      // Relance d'un job déjà passé (refus forcé, nouvel essai après échec) :
      // on retire l'ancienne entrée du journal pour que les compteurs et les
      // clés restent exacts, sans recompter le job dans le total.
      let retriedCount = 0;
      if (!startingFresh) {
        const retriedIds = new Set(
          newJobs
            .map(payrollJobKey)
            .filter((id) => logRef.current.some((e) => e.id === id))
        );
        if (retriedIds.size > 0) {
          logRef.current = logRef.current.filter((e) => !retriedIds.has(e.id));
          setLog(logRef.current);
          completedCountRef.current = Math.max(
            0,
            completedCountRef.current - retriedIds.size
          );
          retriedCount = retriedIds.size;
        }
      }

      totalRef.current += newJobs.length - retriedCount;
      setTotalJobs(totalRef.current);
      queueRef.current.push(...newJobs);
      setQueuedJobs([...queueRef.current]);
      setPhase('running');
      abortRef.current = false;

      if (!processingRef.current) {
        void processQueue();
      }
    },
    [phase, currentJob, clearDismissTimer, processQueue]
  );

  const reset = useCallback(() => {
    abortRef.current = true;
    abortControllerRef.current?.abort();
    stopTick();
    clearDismissTimer();
    queueRef.current = [];
    setQueuedJobs([]);
    logRef.current = [];
    setPhase('idle');
    setLog([]);
    setCurrentJob(null);
    setProgress(0);
    setEstimatedRemainingSec(null);
    setTotalJobs(0);
    setFailedJobs({});
    setRefusedJobs([]);
    setAnnulation(null);
    completedCountRef.current = 0;
    totalRef.current = 0;
    processingRef.current = false;
    abortRef.current = false;
  }, [stopTick, clearDismissTimer]);

  // Le bulletin déjà parti au serveur ne s'annule pas : on le laisse finir et
  // on arrête seulement les suivants (sinon il serait généré sans être compté).
  const cancel = useCallback(() => {
    abortRef.current = true;
    setArretDemande(true);
    queueRef.current = [];
    setQueuedJobs([]);
    stopTick();
  }, [stopTick]);

  /**
   * Ferme le suivi. Les échecs restent : sur leur ligne (« Échec » et sa
   * raison) et dans le récapitulatif, jusqu'à la prochaine génération.
   */
  const dismiss = useCallback(() => {
    const echecs = recapitulatifEchecs(logRef.current);
    reset();
    setRecapEchecs(echecs);
    setFailedJobs(Object.fromEntries(echecs.map((e) => [e.cle, e.raison])));
  }, [reset]);

  const oublierEchecs = useCallback(() => setRecapEchecs([]), []);

  useEffect(
    () => () => {
      stopTick();
      clearDismissTimer();
    },
    [stopTick, clearDismissTimer]
  );

  // Page quittée en pleine génération : la passe s'arrête avec la page. Une
  // note le dit au retour (déclaré avant le `dismiss` de démontage des pages).
  useEffect(
    () => () => {
      if (!processingRef.current || !companyIdRef.current) return;
      noterInterruption(stockageDeSession(), {
        companyId: companyIdRef.current,
        faits: completedCountRef.current,
        total: totalRef.current,
      });
    },
    []
  );

  // Pendant la génération : question avant de fermer l'onglet ou de suivre un
  // lien vers une autre page de l'application.
  useEffect(() => {
    if (phase !== 'running') return undefined;
    const avantDeQuitter = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    const surClic = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const cible = event.target instanceof Element ? event.target : null;
      const lien = cible?.closest('a[href]');
      if (!lien) return;
      const quitte = lienQuitteLaPage(
        {
          href: lien.getAttribute('href'),
          target: lien.getAttribute('target'),
          download: lien.hasAttribute('download'),
        },
        window.location
      );
      if (!quitte) return;
      if (window.confirm(questionQuitterGeneration(completedCountRef.current, totalRef.current))) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
    };
    window.addEventListener('beforeunload', avantDeQuitter);
    document.addEventListener('click', surClic, true);
    return () => {
      window.removeEventListener('beforeunload', avantDeQuitter);
      document.removeEventListener('click', surClic, true);
    };
  }, [phase]);

  const currentLabel = currentJob
    ? `Génération du bulletin de ${monthYearLabel(currentJob.month, currentJob.year)} — ${currentJob.employeeName}…`
    : null;

  const isRunning = phase === 'running';

  const generateJobs = useCallback(
    (jobs: PayrollGenerationJob[]) => {
      enqueueJobs(jobs);
    },
    [enqueueJobs]
  );

  /**
   * Relance uniquement les jobs refusés par une garde, avec le flag de forçage
   * correspondant. À n'appeler que depuis un clic explicite de l'utilisateur
   * (dialogue de refus / récapitulatif) — jamais automatiquement.
   */
  const forceRefused = useCallback(() => {
    // Les refus d'heures sur un arrêt et d'arrêts illisibles ne se forcent jamais.
    const forcables = refusForcablesEnGroupe(refusedJobs);
    if (forcables.length === 0) return;
    const jobs = forcables.map(({ job, code }) => ({
      ...job,
      forceCalendrierIncomplet:
        job.forceCalendrierIncomplet || code === 'calendrier_incomplet',
      regenererBulletinValide:
        job.regenererBulletinValide || code === 'bulletin_valide',
    }));
    enqueueJobs(jobs);
  }, [refusedJobs, enqueueJobs]);

  /**
   * Relance un job refusé tel quel, sans forçage : après « effacer ces heures »
   * ou pour réessayer quand les arrêts n'ont pas pu être lus.
   */
  const retryJob = useCallback(
    (job: PayrollGenerationJob) => {
      enqueueJobs([job]);
    },
    [enqueueJobs]
  );

  const completedCount = log.length;

  return {
    phase,
    log,
    currentJob,
    queuedJobs,
    currentLabel,
    progress,
    estimatedRemainingSec,
    totalJobs,
    completedCount,
    isRunning,
    generateJobs,
    failedJobs,
    refusedJobs,
    recapEchecs,
    annulation,
    arretDemande,
    oublierEchecs,
    forceRefused,
    retryJob,
    reset,
    cancel,
    dismiss,
  };
}

/**
 * Checklist d'onboarding d'un salarié (RH ou collaborateur concerné).
 */

import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  FileText,
  GraduationCap,
  Key,
  Loader2,
  Monitor,
  Printer,
  Users,
} from "lucide-react";

import {
  completeTask,
  getMyOnboarding,
  getOnboarding,
  uncompleteTask,
  type OnboardingTask,
} from "@/api/onboarding";
import { getEmployee } from "@/api/employees";
import { pageTitleClassName } from '@/components/layout';
import {
  EmployeePageHeader,
  EmployeePageShell,
} from "@/components/employee/EmployeePageHeader";
import { OnboardingHubPage } from "@/components/onboarding/OnboardingHubPage";
import { OnboardingKpiBand } from "@/components/onboarding/OnboardingKpiBand";
import { OnboardingTaskItem } from "@/components/onboarding/OnboardingTaskItem";
import { EmployeeOnboardingCompletion } from "@/features/employee-detail/components/EmployeeOnboardingCompletion";
import { EmployeeProfileEditDialog } from "@/features/employee-detail/components/EmployeeProfileEditDialog";
import { isProfileIncomplete } from "@/features/employee-detail/components/employeeProfileFormUtils";
import { OnboardingTimeline } from "@/components/onboarding/OnboardingTimeline";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useToast } from "@/components/ui/use-toast";
import {
  buildTimelineMilestones,
  countTaskStats,
  filterTasks,
  formatEmployeeMetaLine,
  sortTasksByUrgency,
  type OnboardingEmployeeHeader,
  type TaskFilter,
} from "@/lib/onboardingUtils";

export { OnboardingHubPage };

const CATEGORY_ORDER = ["administratif", "materiel", "acces", "formation", "social"] as const;

const CATEGORY_META: Record<string, { label: string; icon: typeof FileText }> = {
  administratif: { label: "Administratif", icon: FileText },
  materiel: { label: "Matériel", icon: Monitor },
  acces: { label: "Accès", icon: Key },
  formation: { label: "Formation", icon: GraduationCap },
  social: { label: "Social", icon: Users },
};

function groupTasksByCategory(tasks: OnboardingTask[]) {
  const map = new Map<string, OnboardingTask[]>();
  for (const t of tasks) {
    const c = (t.category || "autre").toLowerCase();
    if (!map.has(c)) map.set(c, []);
    map.get(c)!.push(t);
  }
  return map;
}

export function EmployeeOnboardingRedirect() {
  const navigate = useNavigate();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? "";

  const { data, isPending, isError, isSuccess } = useQuery({
    queryKey: ["onboarding", "me", companyId],
    queryFn: () => getMyOnboarding(companyId),
    enabled: Boolean(companyId),
    retry: false,
  });

  useEffect(() => {
    if (isSuccess && data?.employee_id) {
      navigate(`/onboarding/${data.employee_id}`, { replace: true });
    }
  }, [isSuccess, data?.employee_id, navigate]);

  if (!companyId) {
    return (
      <div className="mx-auto max-w-lg">
        <Card>
          <CardHeader>
            <CardTitle>Onboarding</CardTitle>
            <p className="text-sm text-muted-foreground">
              Sélectionnez une entreprise pour continuer.
            </p>
          </CardHeader>
        </Card>
      </div>
    );
  }

  if (isPending) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isError || !data?.employee_id) {
    return (
      <div className="mx-auto max-w-lg">
        <Card>
          <CardHeader>
            <CardTitle>Onboarding</CardTitle>
            <p className="text-sm text-muted-foreground">Checklist personnelle</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground leading-relaxed">
              Votre checklist d&apos;onboarding n&apos;est pas encore disponible.
            </p>
            <Button asChild variant="outline" size="sm">
              <Link to="/employee/formation">Retour à Ma formation</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 p-8 text-muted-foreground">
      <Loader2 className="h-8 w-8 animate-spin" />
      <p className="text-sm">Ouverture de votre checklist…</p>
    </div>
  );
}

export default function OnboardingPage() {
  const { employeeId } = useParams<{ employeeId: string }>();
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? "";
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [taskFilter, setTaskFilter] = useState<TaskFilter>("all");
  const [profileEditOpen, setProfileEditOpen] = useState(false);

  const isRh =
    user?.role === "rh" ||
    user?.role === "admin" ||
    user?.role === "collaborateur_rh";

  const isEmployeeView = !isRh;

  const {
    data: checklist,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["onboarding", employeeId, companyId],
    queryFn: () => getOnboarding(employeeId!, companyId),
    enabled: Boolean(employeeId && companyId),
    retry: false,
  });

  const { data: employee } = useQuery({
    queryKey: ["employee-header", employeeId, companyId],
    queryFn: () => getEmployee(employeeId!),
    enabled: Boolean(employeeId && companyId && checklist),
  });

  const profileIncomplete = employee ? isProfileIncomplete(employee) : false;

  const hireDate = employee?.hire_date ?? null;

  const filteredTasks = useMemo(() => {
    if (!checklist) return [];
    return filterTasks(checklist.tasks, taskFilter, hireDate);
  }, [checklist, taskFilter, hireDate]);

  const byCategory = useMemo(
    () => groupTasksByCategory(filteredTasks),
    [filteredTasks],
  );

  const taskStats = useMemo(
    () => (checklist ? countTaskStats(checklist.tasks, hireDate) : { todo: 0, overdue: 0, done: 0 }),
    [checklist, hireDate],
  );

  const timelineMilestones = useMemo(
    () => (checklist ? buildTimelineMilestones(checklist.tasks, hireDate) : []),
    [checklist, hireDate],
  );

  const completeMut = useMutation({
    mutationFn: (taskId: string) => completeTask(employeeId!, taskId, companyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["onboarding", employeeId, companyId] });
      queryClient.invalidateQueries({ queryKey: ["onboarding", "hub", companyId] });
    },
    onError: () => {
      toast({
        title: "Erreur",
        description: "Impossible de valider la tâche.",
        variant: "destructive",
      });
    },
  });

  const uncompleteMut = useMutation({
    mutationFn: (taskId: string) => uncompleteTask(employeeId!, taskId, companyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["onboarding", employeeId, companyId] });
      queryClient.invalidateQueries({ queryKey: ["onboarding", "hub", companyId] });
    },
    onError: () => {
      toast({
        title: "Erreur",
        description: "Impossible de réinitialiser la tâche.",
        variant: "destructive",
      });
    },
  });

  const toggling = completeMut.isPending || uncompleteMut.isPending;

  const handleTaskToggle = (taskId: string, checked: boolean) => {
    if (checked) completeMut.mutate(taskId);
    else uncompleteMut.mutate(taskId);
  };

  if (!employeeId) {
    return (
      <div>
        <p className="text-muted-foreground">Identifiant salarié manquant.</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-4 w-full max-w-xl" />
        <Skeleton className="h-3 w-full" />
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !checklist) {
    const ax = error as
      | { response?: { status?: number; data?: { detail?: unknown } } }
      | undefined;
    const status = ax?.response?.status;
    const detailRaw = ax?.response?.data?.detail;
    const detail = typeof detailRaw === "string" ? detailRaw : null;
    const message =
      detail ??
      (status === 404
        ? "Cette checklist n'existe pas ou vous n'y avez pas accès."
        : status === 403
          ? "Accès refusé à cette checklist."
          : "Impossible de charger la checklist (réseau ou serveur). Réessayez dans un instant.");

    return (
      <EmployeePageShell className="mx-auto max-w-xl">
        <EmployeePageHeader title="Onboarding" />
        <Card>
          <CardContent className="pt-6 space-y-4">
            <p className="text-sm text-muted-foreground leading-relaxed">{message}</p>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="default"
                disabled={isFetching}
                onClick={() => refetch()}
              >
                {isFetching ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                    Chargement…
                  </>
                ) : (
                  "Réessayer"
                )}
              </Button>
              {isRh ? (
                <Button variant="outline" asChild>
                  <Link to="/onboarding">Tous les onboardings</Link>
                </Button>
              ) : (
                <Button variant="outline" asChild>
                  <Link to="/employee/formation">Retour à Ma formation</Link>
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </EmployeePageShell>
    );
  }

  const fullName = employee
    ? `${employee.first_name} ${employee.last_name}`.trim()
    : "Salarié";
  const metaLine = employee ? formatEmployeeMetaLine(employee) : null;
  const pageTitle = isEmployeeView ? "Mon parcours d'intégration" : fullName;

  return (
    <EmployeePageShell className="mx-auto max-w-4xl pb-6 print:p-4">
      {isRh ? (
        <div className="print:hidden">
          <Button variant="ghost" size="sm" className="-ml-2 h-8 text-muted-foreground" asChild>
            <Link to="/onboarding">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Tous les onboardings
            </Link>
          </Button>
        </div>
      ) : null}

      {isRh && employeeId && employee ? (
        <>
          <EmployeeProfileEditDialog
            open={profileEditOpen}
            onOpenChange={setProfileEditOpen}
            employeeId={employeeId}
            employee={employee}
            variant={profileIncomplete ? "onboarding" : "edit"}
            onSuccess={(updated) => {
              queryClient.setQueryData(["employee-header", employeeId, companyId], updated);
              queryClient.invalidateQueries({ queryKey: ["onboarding", "hub", companyId] });
            }}
          />
          <EmployeeOnboardingCompletion
            employeeId={employeeId}
            employee={employee}
            onOpenEdit={() => setProfileEditOpen(true)}
          />
        </>
      ) : null}

      {isEmployeeView ? (
        <Alert className="print:hidden border-primary/20 bg-primary/5">
          <AlertDescription className="text-sm leading-relaxed">
            Vous voyez ici toutes les étapes prévues pour votre intégration. Certaines actions
            sont réalisées par les équipes RH, IT ou votre manager — vous pouvez suivre
            l&apos;avancement sans les modifier.
          </AlertDescription>
        </Alert>
      ) : null}

      {isEmployeeView ? (
        <EmployeePageHeader
          title={pageTitle}
          description={metaLine ?? undefined}
          afterDescription={
            checklist.completed_at ? (
              <Badge className="bg-emerald-600 hover:bg-emerald-600 w-fit">Terminé</Badge>
            ) : null
          }
          actions={
            <div className="flex flex-wrap items-center gap-2 shrink-0 print:hidden">
              {!checklist.completed_at ? (
                <span className="text-sm text-muted-foreground tabular-nums">
                  {checklist.progress_pct.toFixed(0)} %
                </span>
              ) : null}
            </div>
          }
          className="print:block"
        />
      ) : (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between print:block">
          <div>
            <h1 className={pageTitleClassName}>{pageTitle}</h1>
            {employee?.job_title ? (
              <p className="text-muted-foreground text-sm mt-1">{employee.job_title}</p>
            ) : null}
            {metaLine ? (
              <p className="text-xs text-muted-foreground mt-2 leading-relaxed max-w-2xl">
                {metaLine}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-2 shrink-0 print:hidden">
          {checklist.completed_at ? (
            <Badge className="bg-emerald-600 hover:bg-emerald-600">Terminé</Badge>
          ) : null}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => window.print()}
          >
            <Printer className="mr-2 h-4 w-4" />
            Imprimer
          </Button>
          </div>
        </div>
      )}

      <Card className="print:shadow-none print:border">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Progression globale</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <OnboardingKpiBand stats={taskStats} />
          <OnboardingTimeline milestones={timelineMilestones} />
          <Progress value={checklist.progress_pct} className="h-2" />
          <p className="text-sm text-muted-foreground tabular-nums">
            {checklist.nb_completed} / {checklist.nb_total} tâches complétées (
            {checklist.progress_pct.toFixed(0)}%)
          </p>
        </CardContent>
      </Card>

      <div className="print:hidden">
        <ToggleGroup
          type="single"
          value={taskFilter}
          onValueChange={(v) => {
            if (v) setTaskFilter(v as TaskFilter);
          }}
          className="flex flex-wrap justify-start"
        >
          <ToggleGroupItem value="all">Toutes</ToggleGroupItem>
          <ToggleGroupItem value="todo">À faire</ToggleGroupItem>
          <ToggleGroupItem value="overdue">En retard</ToggleGroupItem>
          <ToggleGroupItem value="done">Faites</ToggleGroupItem>
        </ToggleGroup>
      </div>

      {filteredTasks.length === 0 && taskFilter !== "all" ? (
        <p className="text-sm text-muted-foreground print:hidden">
          Aucune tâche ne correspond à ce filtre.
        </p>
      ) : null}

      {CATEGORY_ORDER.map((cat) => {
        const tasks = byCategory.get(cat);
        if (!tasks?.length) return null;
        const sorted = sortTasksByUrgency(tasks, hireDate);
        const meta = CATEGORY_META[cat] ?? { label: cat, icon: FileText };
        const Icon = meta.icon;
        const done = tasks.filter((t) => t.is_completed).length;
        return (
          <section key={cat} className="space-y-3 print:break-inside-avoid-page">
            <h2 className="text-sm font-semibold flex items-center gap-2 border-b pb-2">
              <Icon className="h-4 w-4 text-muted-foreground" />
              {meta.label}{" "}
              <span className="text-muted-foreground font-normal tabular-nums">
                {done}/{tasks.length}
              </span>
            </h2>
            <ul className="space-y-2">
              {sorted.map((t) => (
                <OnboardingTaskItem
                  key={t.id}
                  task={t}
                  employeeId={employeeId}
                  hireDate={hireDate}
                  isRh={isRh}
                  onToggle={handleTaskToggle}
                  toggling={toggling}
                />
              ))}
            </ul>
          </section>
        );
      })}

      {checklist.created_at ? (
        <p className="text-[11px] text-muted-foreground text-center pt-4 border-t">
          Checklist créée le{" "}
          {new Date(checklist.created_at).toLocaleString("fr-FR", {
            dateStyle: "long",
            timeStyle: "short",
          })}
        </p>
      ) : null}
    </EmployeePageShell>
  );
}

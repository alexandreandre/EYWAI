import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import {
  CalendarCheck,
  CheckCircle2,
  CreditCard,
  FileCheck,
  FileWarning,
  FlaskConical,
  Landmark,
  ListTodo,
  Loader2,
  PartyPopper,
  Stethoscope,
  UserPlus,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { KPIs } from "@/api/medicalFollowUp";

const STORAGE_KEY_REAL = "eywai.dashboard.priorityTask.validatedIds.v1";
const STORAGE_KEY_DEMO = "eywai.dashboard.priorityTask.validatedIds.demo.v1";
const DEMO_MODE_KEY = "eywai.dashboard.priorityTask.demoMode";

const isDev = import.meta.env.DEV;

/**
 * Données fictives temporaires pour valider le flux UX.
 * On ne force volontairement que 3 catégories pour un test rapide.
 */
const DEMO_PRIORITY_INPUTS: {
  actions: ActionItemsSlice;
  alerts: AlertItemsSlice;
  residenceStats: ResidencePermitSlice;
  medicalEnabled: boolean;
  medicalKpis: KPIs;
  ribTotal: number;
} = {
  actions: { pendingAbsences: 1, pendingExpenses: 1 },
  alerts: { obsoleteRates: 1, expiringContracts: 0, endOfTrialPeriods: 0 },
  residenceStats: { total_expire: 0, total_a_renouveler: 0, total_a_renseigner: 0 },
  medicalEnabled: false,
  medicalKpis: {
    overdue_count: 0,
    due_within_30_count: 0,
    active_total: 0,
    completed_this_month: 0,
  },
  ribTotal: 0,
};

export type ActionItemsSlice = {
  pendingAbsences: number;
  pendingExpenses: number;
};

export type AlertItemsSlice = {
  obsoleteRates: number;
  expiringContracts: number;
  endOfTrialPeriods: number;
};

export type ResidencePermitSlice = {
  total_expire: number;
  total_a_renouveler: number;
  total_a_renseigner: number;
};

export type PriorityTaskId =
  | "leaves"
  | "expenses"
  | "rib"
  | "medical"
  | "residence"
  | "rates"
  | "employees";

type PriorityTask = {
  id: PriorityTaskId;
  title: string;
  description: string;
  count: number;
  href: string;
  icon: LucideIcon;
};

function readValidatedIds(demo: boolean): PriorityTaskId[] {
  const key = demo ? STORAGE_KEY_DEMO : STORAGE_KEY_REAL;
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    const allowed: PriorityTaskId[] = [
      "leaves",
      "expenses",
      "rib",
      "medical",
      "residence",
      "rates",
      "employees",
    ];
    return parsed.filter((x): x is PriorityTaskId => typeof x === "string" && allowed.includes(x as PriorityTaskId));
  } catch {
    return [];
  }
}

function writeValidatedIds(ids: PriorityTaskId[], demo: boolean) {
  const key = demo ? STORAGE_KEY_DEMO : STORAGE_KEY_REAL;
  sessionStorage.setItem(key, JSON.stringify(ids));
}

/** Ordre fixe : aligné sur l’importance métier (mêmes sources que les pastilles sidebar + RIB). */
const PRIORITY_ORDER: PriorityTaskId[] = [
  "leaves",
  "expenses",
  "rib",
  "medical",
  "residence",
  "rates",
  "employees",
];

function buildQueue(
  actions: ActionItemsSlice,
  alerts: AlertItemsSlice,
  residence: ResidencePermitSlice | null,
  medicalEnabled: boolean,
  medicalKpis: KPIs | null,
  ribTotal: number,
): PriorityTask[] {
  const residenceTotal = residence
    ? residence.total_expire + residence.total_a_renouveler + residence.total_a_renseigner
    : 0;
  const medicalTotal =
    medicalEnabled && medicalKpis ? medicalKpis.overdue_count + medicalKpis.due_within_30_count : 0;
  const employeesTotal = alerts.expiringContracts + alerts.endOfTrialPeriods;

  const byId: Record<PriorityTaskId, PriorityTask | null> = {
    leaves:
      actions.pendingAbsences > 0
        ? {
            id: "leaves",
            title: "Demandes d'absences",
            description: "Demandes en attente de validation.",
            count: actions.pendingAbsences,
            href: "/leaves",
            icon: CalendarCheck,
          }
        : null,
    expenses:
      actions.pendingExpenses > 0
        ? {
            id: "expenses",
            title: "Notes de frais",
            description: "Notes de frais à traiter.",
            count: actions.pendingExpenses,
            href: "/expenses",
            icon: CreditCard,
          }
        : null,
    rib:
      ribTotal > 0
        ? {
            id: "rib",
            title: "Alertes RIB",
            description: "Modification ou doublon de RIB à examiner.",
            count: ribTotal,
            href: "/employees",
            icon: Landmark,
          }
        : null,
    medical:
      medicalTotal > 0
        ? {
            id: "medical",
            title: "Suivi médical",
            description: "Visites à planifier ou en retard.",
            count: medicalTotal,
            href: "/medical-follow-up",
            icon: Stethoscope,
          }
        : null,
    residence:
      residenceTotal > 0
        ? {
            id: "residence",
            title: "Titres de séjour",
            description: "Titres expirés, à renouveler ou à renseigner.",
            count: residenceTotal,
            href: "/residence-permits",
            icon: FileCheck,
          }
        : null,
    rates:
      alerts.obsoleteRates > 0
        ? {
            id: "rates",
            title: "Taux de cotisations",
            description: "Taux obsolètes à mettre à jour.",
            count: alerts.obsoleteRates,
            href: "/rates",
            icon: FileWarning,
          }
        : null,
    employees:
      employeesTotal > 0
        ? {
            id: "employees",
            title: "Contrats & périodes d'essai",
            description: "Contrats qui se terminent ou fins de période d'essai.",
            count: employeesTotal,
            href: "/employees",
            icon: UserPlus,
          }
        : null,
  };

  return PRIORITY_ORDER.map((id) => byId[id]).filter((t): t is PriorityTask => t != null);
}

export function PriorityTaskTab(props: {
  actions: ActionItemsSlice;
  alerts: AlertItemsSlice;
  residenceStats: ResidencePermitSlice | null;
  medicalEnabled: boolean;
  medicalKpis: KPIs | null;
  ribTotal: number;
  loading: boolean;
}) {
  const [demoMode, setDemoMode] = useState(
    () => isDev && typeof sessionStorage !== "undefined" && sessionStorage.getItem(DEMO_MODE_KEY) === "1",
  );

  const [validatedIds, setValidatedIds] = useState<PriorityTaskId[]>(() =>
    readValidatedIds(isDev && typeof sessionStorage !== "undefined" && sessionStorage.getItem(DEMO_MODE_KEY) === "1"),
  );

  const effectiveLoading = demoMode ? false : props.loading;

  const queueInputs = useMemo(() => {
    if (demoMode) {
      return {
        actions: DEMO_PRIORITY_INPUTS.actions,
        alerts: DEMO_PRIORITY_INPUTS.alerts,
        residenceStats: DEMO_PRIORITY_INPUTS.residenceStats,
        medicalEnabled: DEMO_PRIORITY_INPUTS.medicalEnabled,
        medicalKpis: DEMO_PRIORITY_INPUTS.medicalKpis,
        ribTotal: DEMO_PRIORITY_INPUTS.ribTotal,
      };
    }
    return {
      actions: props.actions,
      alerts: props.alerts,
      residenceStats: props.residenceStats,
      medicalEnabled: props.medicalEnabled,
      medicalKpis: props.medicalKpis,
      ribTotal: props.ribTotal,
    };
  }, [demoMode, props.actions, props.alerts, props.residenceStats, props.medicalEnabled, props.medicalKpis, props.ribTotal]);

  const queue = useMemo(
    () =>
      buildQueue(
        queueInputs.actions,
        queueInputs.alerts,
        queueInputs.residenceStats,
        queueInputs.medicalEnabled,
        queueInputs.medicalKpis,
        queueInputs.ribTotal,
      ),
    [queueInputs],
  );

  const pending = useMemo(
    () => queue.filter((t) => !validatedIds.includes(t.id)),
    [queue, validatedIds],
  );

  const current = pending[0] ?? null;
  const remainingAfter = pending.length > 1 ? pending.length - 1 : 0;
  /** Position dans la file de types (1 = première catégorie à traiter). */
  const currentStepInFile = current ? queue.length - pending.length + 1 : 0;

  const persistValidated = useCallback((next: PriorityTaskId[]) => {
    setValidatedIds(next);
    writeValidatedIds(next, demoMode);
  }, [demoMode]);

  const handleValidate = () => {
    if (!current) return;
    persistValidated([...validatedIds, current.id]);
  };

  const handleResetQueue = () => {
    persistValidated([]);
  };

  const setDemoModeOn = (on: boolean) => {
    if (!isDev) return;
    if (on) {
      sessionStorage.setItem(DEMO_MODE_KEY, "1");
      setDemoMode(true);
      setValidatedIds(readValidatedIds(true));
    } else {
      sessionStorage.removeItem(DEMO_MODE_KEY);
      setDemoMode(false);
      setValidatedIds(readValidatedIds(false));
    }
  };

  if (effectiveLoading) {
    return (
      <div className="flex min-h-[280px] items-center justify-center rounded-lg border border-dashed bg-muted/30">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" aria-hidden />
        <span className="sr-only">Chargement des tâches</span>
      </div>
    );
  }

  const devDemoBanner =
    isDev ? (
      <Card className="border-dashed border-amber-300/80 bg-amber-50/50">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <FlaskConical className="h-5 w-5 text-amber-700" aria-hidden />
            Mode démo (développement)
          </CardTitle>
          <CardDescription>
            Active une file fictive de 3 tâches pour tester « Valider et passer à la suivante » sans données
            réelles. Les validations sont stockées à part (session).
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {!demoMode ? (
            <Button type="button" variant="secondary" onClick={() => setDemoModeOn(true)}>
              Activer la file démo
            </Button>
          ) : (
            <Button type="button" variant="outline" onClick={() => setDemoModeOn(false)}>
              Revenir aux données réelles
            </Button>
          )}
        </CardContent>
      </Card>
    ) : null;

  if (queue.length === 0) {
    return (
      <div className="space-y-4">
        {devDemoBanner}
        <Card className="border-emerald-200/80 bg-emerald-50/40">
          <CardHeader>
            <div className="flex items-center gap-2">
              <PartyPopper className="h-6 w-6 text-emerald-600" aria-hidden />
              <CardTitle className="text-lg">Rien à traiter pour l’instant</CardTitle>
            </div>
            <CardDescription>
              Aucune alerte ne correspond aux indicateurs du tableau de bord (congés, frais, taux, équipe, etc.).
              {isDev && !demoMode && (
                <span className="mt-2 block text-muted-foreground">
                  Astuce : activez la file démo ci-dessus pour tester « Valider » sans créer de données.
                </span>
              )}
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  if (!current) {
    return (
      <div className="space-y-4">
        {devDemoBanner}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <ListTodo className="h-5 w-5" />
              File parcourue
            </CardTitle>
            <CardDescription>
              Vous avez fait défiler toutes les catégories en attente. Réinitialisez pour revoir la priorité depuis le
              début, ou rafraîchissez la page une fois les actions réellement traitées dans les modules.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button type="button" variant="secondary" onClick={handleResetQueue}>
              Réinitialiser la file
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const Icon = current.icon;

  return (
    <div className="space-y-4">
      {devDemoBanner}
      {demoMode && (
        <p className="text-xs text-amber-900/80">
          File démo : {queue.length} catégories à enchaîner — le badge indique l’étape, pas le nombre d’éléments métier.
        </p>
      )}
      <Card className="border-primary/25 shadow-sm">
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <Icon className="h-6 w-6 shrink-0 text-primary" aria-hidden />
              <div>
                <CardTitle className="text-xl leading-tight">{current.title}</CardTitle>
                <CardDescription className="mt-1">{current.description}</CardDescription>
                {demoMode && (
                  <p className="mt-2 text-sm font-medium text-foreground">
                    Catégorie {currentStepInFile} sur {queue.length}
                  </p>
                )}
              </div>
            </div>
            <div className="flex flex-col items-end gap-1">
              {demoMode ? (
                <>
                  <Badge variant="destructive" className="shrink-0 tabular-nums text-sm px-2.5 py-0.5">
                    {currentStepInFile}/{queue.length}
                  </Badge>
                  <span className="text-[10px] text-muted-foreground leading-tight text-right max-w-[7rem]">
                    étape dans la file
                  </span>
                </>
              ) : (
                <Badge variant="destructive" className="shrink-0 tabular-nums" title="Éléments à traiter dans ce module">
                  {current.count}
                </Badge>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Une seule priorité à la fois : les autres types d’alertes restent dans la file jusqu’à ce que vous les
            validiez ici (après traitement dans le module concerné).
          </p>
          {remainingAfter > 0 && (
            <p className="text-sm font-medium text-muted-foreground">
              <span className="text-foreground">{remainingAfter}</span> autre{remainingAfter > 1 ? "s" : ""} type
              {remainingAfter > 1 ? "s" : ""} d’alerte en file derrière celle-ci.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button type="button" asChild>
              <Link to={current.href}>Ouvrir le module</Link>
            </Button>
            <Button type="button" variant="default" className="gap-1.5 bg-emerald-600 hover:bg-emerald-700" onClick={handleValidate}>
              <CheckCircle2 className="h-4 w-4" />
              Valider et passer à la suivante
            </Button>
          </div>
          <button
            type="button"
            onClick={handleResetQueue}
            className="text-xs text-muted-foreground underline-offset-4 hover:underline"
          >
            Réinitialiser la file d’affichage
          </button>
        </CardContent>
      </Card>
    </div>
  );
}

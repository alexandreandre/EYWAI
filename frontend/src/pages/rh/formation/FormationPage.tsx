// Page RH unifiée Pack Talent — /formation (+ hash par onglet)

import { RhPageHeader } from '@/components/layout';
import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Settings } from "lucide-react";
import { SharkFinLoader } from '@/components/SharkFinLoader';

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { getDashboardCounts } from "@/api/certifications";
import { getOverdueCount } from "@/api/legalObligations";
import {
  HASH_BY_TAB,
  isFormationTabId,
  parseFormationRoute,
  type FormationLegacySub,
  type FormationTabId,
} from "@/pages/rh/formation/formationTabRouting";
import type { ParametresSubTab } from "@/features/formation/components/tabs/ParametresTab";

const LazyPilotageTab = lazy(() => import("@/features/formation/components/tabs/PilotageTab"));
const LazyFormationsTab = lazy(() => import("@/features/formation/components/tabs/FormationsTab"));
const LazyConformiteTab = lazy(() => import("@/features/formation/components/tabs/ConformiteTab"));
const LazyAnnualReviews = lazy(() => import("@/pages/rh/AnnualReviews"));
const LazyDeveloppementTab = lazy(() => import("@/features/formation/components/tabs/DeveloppementTab"));
const LazyParametresTab = lazy(() => import("@/features/formation/components/tabs/ParametresTab"));

const DEFAULT_SUB_BY_TAB: Partial<Record<FormationTabId, string>> = {
  formations: "inscriptions",
  conformite: "habilitations",
  developpement: "objectifs",
  parametres: "trames",
};

const PARAMETRES_SUBS = new Set<ParametresSubTab>(["trames", "habilitations", "competences"]);

function parseParametresSubFromSearch(): ParametresSubTab | undefined {
  const sub = new URLSearchParams(window.location.search).get("sub");
  if (sub && PARAMETRES_SUBS.has(sub as ParametresSubTab)) {
    return sub as ParametresSubTab;
  }
  return undefined;
}

function TabFallback() {
  return (
    <div className="rounded-lg border border-dashed bg-muted/20">
      <SharkFinLoader variant="fullPage" label="Chargement de l'onglet…" className="min-h-[240px]" />
    </div>
  );
}

export default function FormationPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [tab, setTab] = useState<FormationTabId>(() => parseFormationRoute().tab);
  const [legacySub, setLegacySub] = useState<FormationLegacySub | undefined>(
    () => parseFormationRoute().legacySub,
  );
  const [parametresSub, setParametresSub] = useState<ParametresSubTab>(() => {
    const route = parseFormationRoute();
    if (route.tab === "parametres") {
      return parseParametresSubFromSearch() ?? "trames";
    }
    return "trames";
  });

  const certCountsQuery = useQuery({
    queryKey: ["formation-page", "cert-dashboard-counts"],
    queryFn: () => getDashboardCounts(),
  });
  const overdueQuery = useQuery({
    queryKey: ["formation-page", "legal-overdue-count"],
    queryFn: () => getOverdueCount(),
  });

  const expired = certCountsQuery.data?.expired ?? 0;
  const expiring = certCountsQuery.data?.expiring ?? 0;
  const overdue = overdueQuery.data?.count ?? 0;

  const syncFromLocation = useCallback(() => {
    const route = parseFormationRoute();
    setTab(route.tab);
    setLegacySub(route.legacySub);
    if (route.tab === "parametres") {
      setParametresSub(parseParametresSubFromSearch() ?? "trames");
    }
  }, []);

  useEffect(() => {
    syncFromLocation();
  }, [location.pathname, location.hash, location.search, syncFromLocation]);

  const navigateToTab = (value: FormationTabId, sub?: string) => {
    const params = new URLSearchParams();
    const resolvedSub = sub ?? DEFAULT_SUB_BY_TAB[value];
    if (resolvedSub) params.set("sub", resolvedSub);
    const search = params.toString();
    navigate(
      {
        pathname: "/formation",
        hash: HASH_BY_TAB[value],
        search: search ? `?${search}` : "",
      },
      { replace: true },
    );
  };

  const handleTabChange = (value: string) => {
    if (!isFormationTabId(value)) return;
    setTab(value);
    setLegacySub(undefined);
    if (value === "parametres") {
      const nextSub = parseParametresSubFromSearch() ?? parametresSub;
      setParametresSub(nextSub);
      navigateToTab(value, nextSub);
      return;
    }
    navigateToTab(value);
  };

  const openParametres = (sub: ParametresSubTab = "trames") => {
    setParametresSub(sub);
    setTab("parametres");
    setLegacySub(undefined);
    navigateToTab("parametres", sub);
  };

  const conformiteBadge = useMemo(() => {
    const total = expired + overdue;
    if (total > 0) {
      return (
        <Badge className="ml-1 border-0 bg-red-600 px-1.5 text-[10px] text-white">{total}</Badge>
      );
    }
    if (expiring > 0) {
      return (
        <Badge className="ml-1 border-0 bg-orange-500 px-1.5 text-[10px] text-white">{expiring}</Badge>
      );
    }
    return null;
  }, [expired, expiring, overdue]);

  return (
    <div className="space-y-6">
      <RhPageHeader
        title="Formation & Talents"
        description="Piloter formations, conformité et entretiens."
      />

      <Tabs value={tab} onValueChange={handleTabChange} className="w-full">
        <TabsList className="mb-4 flex h-auto min-h-11 w-full flex-wrap justify-start gap-1">
          <TabsTrigger value="pilotage">Pilotage</TabsTrigger>
          <TabsTrigger value="formations">Formations</TabsTrigger>
          <TabsTrigger value="conformite" className="gap-0">
            <span className="inline-flex items-center justify-center">
              Conformité
              {conformiteBadge}
            </span>
          </TabsTrigger>
          <TabsTrigger value="entretiens">Entretiens</TabsTrigger>
          <TabsTrigger value="developpement">Développement</TabsTrigger>
          <TabsTrigger value="parametres" className="gap-1.5">
            <Settings className="h-4 w-4 shrink-0" />
            Paramètres
          </TabsTrigger>
        </TabsList>

        <div className="mt-0 min-h-[200px]">
          {tab === "pilotage" && (
            <Suspense fallback={<TabFallback />}>
              <LazyPilotageTab />
            </Suspense>
          )}
          {tab === "formations" && (
            <Suspense fallback={<TabFallback />}>
              <LazyFormationsTab initialSub={legacySub} />
            </Suspense>
          )}
          {tab === "conformite" && (
            <Suspense fallback={<TabFallback />}>
              <LazyConformiteTab initialSub={legacySub} />
            </Suspense>
          )}
          {tab === "entretiens" && (
            <Suspense fallback={<TabFallback />}>
              <LazyAnnualReviews
                embedded
                fromFormationHub
                onManageTemplates={() => openParametres("trames")}
              />
            </Suspense>
          )}
          {tab === "developpement" && (
            <Suspense fallback={<TabFallback />}>
              <LazyDeveloppementTab initialSub={legacySub} />
            </Suspense>
          )}
          {tab === "parametres" && (
            <Suspense fallback={<TabFallback />}>
              <LazyParametresTab initialSub={parametresSub} />
            </Suspense>
          )}
        </div>
      </Tabs>
    </div>
  );
}

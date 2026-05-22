// frontend/src/pages/CSE.tsx
// Page RH : Module CSE & Dialogue Social

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Loader2,
  Users,
  Calendar,
  Clock,
  FileText,
  CalendarDays,
  Download,
  ChevronDown,
  AlertTriangle,
} from "lucide-react";
import {
  getMandateAlerts,
  getElectionAlerts,
  getMeetings,
  getElectedMembers,
  getDelegationSummary,
} from "@/api/cse";
import type { MandateAlert, ElectionAlert } from "@/api/cse";
import { CsePageProvider } from "@/contexts/CsePageContext";
import {
  type CseTabId,
  isCseTabId,
  formatPluralAutres,
} from "@/lib/cseLabels";
import { getCurrentMonthPeriod } from "@/lib/csePeriod";
import { cn } from "@/lib/utils";
import { CseExportsMenu } from "@/components/cse/CseExportsMenu";

import MeetingsTab from "./cse/MeetingsTab";
import ElectedMembersTab from "./cse/ElectedMembersTab";
import DelegationHoursTab from "./cse/DelegationHoursTab";
import BDESTab from "./cse/BDESTab";
import ElectionCalendarTab from "./cse/ElectionCalendarTab";
import ExportsTab from "./cse/ExportsTab";

function AlertLineButton({
  children,
  onClick,
  className,
}: {
  children: ReactNode;
  onClick: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full text-left text-sm rounded-md px-2 py-1.5 -mx-2 hover:bg-muted/80 transition-colors",
        className,
      )}
    >
      {children}
    </button>
  );
}

export default function CSE() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const highlightParam = searchParams.get("highlight");

  const [activeTab, setActiveTabState] = useState<CseTabId>(
    isCseTabId(tabParam) ? tabParam : "meetings",
  );
  const [highlightElectedMemberId, setHighlightElectedMemberId] = useState<string | null>(
    highlightParam,
  );
  const [alertsOpen, setAlertsOpen] = useState(false);

  const setActiveTab = useCallback(
    (tab: CseTabId) => {
      setActiveTabState(tab);
      const next = new URLSearchParams(searchParams);
      next.set("tab", tab);
      if (tab !== "elected") {
        next.delete("highlight");
        setHighlightElectedMemberId(null);
      }
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  useEffect(() => {
    if (isCseTabId(tabParam) && tabParam !== activeTab) {
      setActiveTabState(tabParam);
    }
  }, [tabParam, activeTab]);

  useEffect(() => {
    if (highlightParam) {
      setHighlightElectedMemberId(highlightParam);
    }
  }, [highlightParam]);

  const { data: mandateAlerts = [], isLoading: loadingMandateAlerts } = useQuery({
    queryKey: ["cse", "mandate-alerts"],
    queryFn: () => getMandateAlerts(3),
  });

  const { data: electionAlerts = [], isLoading: loadingElectionAlerts } = useQuery({
    queryKey: ["cse", "election-alerts"],
    queryFn: () => getElectionAlerts(),
  });

  const { data: upcomingMeetings = [], isLoading: loadingUpcoming } = useQuery({
    queryKey: ["cse", "meetings", "a_venir", "kpi"],
    queryFn: () => getMeetings("a_venir"),
  });

  const { data: electedMembers = [], isLoading: loadingElected } = useQuery({
    queryKey: ["cse", "elected-members", "kpi"],
    queryFn: () => getElectedMembers(true),
  });

  const { periodStart, periodEnd } = getCurrentMonthPeriod();
  const { data: delegationSummary = [] } = useQuery({
    queryKey: ["cse", "delegation-summary", "kpi", periodStart, periodEnd],
    queryFn: () => getDelegationSummary(periodStart, periodEnd),
  });

  const totalAlerts = mandateAlerts.length + electionAlerts.length;
  const delegationOverCount = delegationSummary.filter((s) => s.remaining_hours < 0).length;
  const loadingKpi = loadingMandateAlerts || loadingElectionAlerts || loadingUpcoming || loadingElected;

  const nextMeeting = useMemo(() => {
    if (upcomingMeetings.length === 0) return null;
    return [...upcomingMeetings].sort(
      (a, b) => new Date(a.meeting_date).getTime() - new Date(b.meeting_date).getTime(),
    )[0];
  }, [upcomingMeetings]);

  const contextValue = useMemo(
    () => ({
      activeTab,
      setActiveTab,
      highlightElectedMemberId,
      setHighlightElectedMemberId: (id: string | null) => {
        setHighlightElectedMemberId(id);
        const next = new URLSearchParams(searchParams);
        if (id) next.set("highlight", id);
        else next.delete("highlight");
        setSearchParams(next, { replace: true });
      },
      mandateAlertsCount: mandateAlerts.length,
      electionAlertsCount: electionAlerts.length,
    }),
    [activeTab, setActiveTab, highlightElectedMemberId, mandateAlerts.length, electionAlerts.length, searchParams, setSearchParams],
  );

  const handleMandateAlertClick = (alert: MandateAlert) => {
    setHighlightElectedMemberId(alert.elected_member_id);
    const next = new URLSearchParams(searchParams);
    next.set("tab", "elected");
    next.set("highlight", alert.elected_member_id);
    setSearchParams(next, { replace: true });
    setActiveTabState("elected");
  };

  const handleElectionAlertClick = () => {
    setActiveTab("elections");
  };

  const kpiTiles = [
    {
      key: "mandate",
      label: "Mandats à surveiller",
      value: loadingKpi ? "—" : String(mandateAlerts.length),
      sub: mandateAlerts.length > 0 ? "expiration proche" : "aucune alerte",
      tab: "elected" as CseTabId,
      accent: mandateAlerts.length > 0,
    },
    {
      key: "election",
      label: "Alertes électorales",
      value: loadingKpi ? "—" : String(electionAlerts.length),
      sub: electionAlerts.length > 0 ? "échéances CSE" : "à jour",
      tab: "elections" as CseTabId,
      accent: electionAlerts.length > 0,
    },
    {
      key: "meetings",
      label: "Réunions à venir",
      value: loadingKpi ? "—" : String(upcomingMeetings.length),
      sub: nextMeeting
        ? `${nextMeeting.title} — ${new Date(nextMeeting.meeting_date).toLocaleDateString("fr-FR")}`
        : "aucune planifiée",
      tab: "meetings" as CseTabId,
      accent: false,
    },
    {
      key: "elected",
      label: "Élus actifs",
      value: loadingKpi ? "—" : String(electedMembers.length),
      sub:
        delegationOverCount > 0
          ? `${delegationOverCount} dépassement${delegationOverCount > 1 ? "s" : ""} délégation`
          : "mandats en cours",
      tab: "delegation" as CseTabId,
      accent: delegationOverCount > 0,
    },
  ];

  const tabBadge = (tab: CseTabId): number | undefined => {
    if (tab === "elected" && mandateAlerts.length > 0) return mandateAlerts.length;
    if (tab === "elections" && electionAlerts.length > 0) return electionAlerts.length;
    return undefined;
  };

  return (
    <CsePageProvider value={contextValue}>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">CSE & Dialogue Social</h1>
            <p className="text-muted-foreground mt-1">
              Réunions, élus, délégation, BDES et calendrier électoral
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <CseExportsMenu onOpenExportsTab={() => setActiveTab("exports")} />
            {totalAlerts > 0 && (
              <Badge variant="outline" className="border-orange-300 bg-orange-50 text-orange-900">
                {totalAlerts} alerte{totalAlerts > 1 ? "s" : ""}
              </Badge>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {kpiTiles.map((tile) => (
            <button
              key={tile.key}
              type="button"
              onClick={() => setActiveTab(tile.tab)}
              className={cn(
                "rounded-lg border bg-card p-4 text-left transition-colors hover:bg-muted/50",
                tile.accent && "border-orange-200 bg-orange-50/50",
              )}
            >
              {loadingKpi ? (
                <Skeleton className="h-8 w-12 mb-2" />
              ) : (
                <p className="text-2xl font-semibold tabular-nums">{tile.value}</p>
              )}
              <p className="text-sm font-medium mt-1">{tile.label}</p>
              <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{tile.sub}</p>
            </button>
          ))}
        </div>

        {(mandateAlerts.length > 0 || electionAlerts.length > 0) && (
          <Collapsible open={alertsOpen} onOpenChange={setAlertsOpen}>
            <CollapsibleTrigger className="flex w-full items-center justify-between rounded-lg border px-4 py-3 text-sm font-medium hover:bg-muted/50">
              <span className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-orange-600" />
                Détail des alertes ({totalAlerts})
              </span>
              <ChevronDown
                className={cn("h-4 w-4 transition-transform", alertsOpen && "rotate-180")}
              />
            </CollapsibleTrigger>
            <CollapsibleContent className="pt-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {mandateAlerts.length > 0 && (
                  <Card className="border-orange-200">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base flex items-center gap-2">
                        <Users className="h-4 w-4" />
                        Alertes mandats
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-1">
                        {mandateAlerts.slice(0, 5).map((alert) => (
                          <AlertLineButton
                            key={alert.elected_member_id}
                            onClick={() => handleMandateAlertClick(alert)}
                          >
                            <span className="font-medium">
                              {alert.first_name} {alert.last_name}
                            </span>
                            <span className="text-muted-foreground">
                              {" "}
                              — {alert.days_remaining} j.
                              {alert.months_remaining > 0
                                ? ` (~${alert.months_remaining} mois)`
                                : ""}
                            </span>
                          </AlertLineButton>
                        ))}
                        {mandateAlerts.length > 5 && (
                          <p className="text-sm text-muted-foreground px-2 pt-1">
                            + {mandateAlerts.length - 5} autre
                            {formatPluralAutres(mandateAlerts.length - 5)}
                          </p>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                )}
                {electionAlerts.length > 0 && (
                  <Card className="border-red-200">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base flex items-center gap-2">
                        <CalendarDays className="h-4 w-4" />
                        Alertes électorales
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-1">
                        {electionAlerts.slice(0, 5).map((alert) => (
                          <AlertLineButton
                            key={alert.cycle_id}
                            onClick={handleElectionAlertClick}
                          >
                            <span className="font-medium">{alert.cycle_name}</span>
                            <span className="text-muted-foreground"> — {alert.message}</span>
                          </AlertLineButton>
                        ))}
                        {electionAlerts.length > 5 && (
                          <p className="text-sm text-muted-foreground px-2 pt-1">
                            + {electionAlerts.length - 5} autre
                            {formatPluralAutres(electionAlerts.length - 5)}
                          </p>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )}

        <Tabs value={activeTab} onValueChange={(v) => isCseTabId(v) && setActiveTab(v)} className="space-y-4">
          <TabsList className="flex h-auto w-full flex-wrap justify-start gap-1 bg-muted/50 p-1 md:inline-flex md:flex-nowrap md:overflow-x-auto">
            {(
              [
                { value: "meetings", icon: Calendar, label: "Réunions" },
                { value: "elected", icon: Users, label: "Élus" },
                { value: "delegation", icon: Clock, label: "Délégation" },
                { value: "bdes", icon: FileText, label: "BDES" },
                { value: "elections", icon: CalendarDays, label: "Élections" },
                { value: "exports", icon: Download, label: "Exports" },
              ] as const
            ).map(({ value, icon: Icon, label }) => {
              const badge = tabBadge(value);
              return (
                <TabsTrigger
                  key={value}
                  value={value}
                  className="flex items-center gap-1.5 shrink-0 data-[state=active]:bg-background"
                >
                  <Icon className="h-4 w-4" />
                  <span className="hidden sm:inline">{label}</span>
                  <span className="sm:hidden">{label.slice(0, 4)}.</span>
                  {badge != null && badge > 0 && (
                    <Badge variant="secondary" className="h-5 min-w-5 px-1 text-xs">
                      {badge}
                    </Badge>
                  )}
                </TabsTrigger>
              );
            })}
          </TabsList>

          <TabsContent value="meetings" className="space-y-4">
            <MeetingsTab />
          </TabsContent>
          <TabsContent value="elected" className="space-y-4">
            <ElectedMembersTab />
          </TabsContent>
          <TabsContent value="delegation" className="space-y-4">
            <DelegationHoursTab />
          </TabsContent>
          <TabsContent value="bdes" className="space-y-4">
            <BDESTab />
          </TabsContent>
          <TabsContent value="elections" className="space-y-4">
            <ElectionCalendarTab showHeaderAlerts={false} />
          </TabsContent>
          <TabsContent value="exports" className="space-y-4">
            <ExportsTab />
          </TabsContent>
        </Tabs>
      </div>
    </CsePageProvider>
  );
}

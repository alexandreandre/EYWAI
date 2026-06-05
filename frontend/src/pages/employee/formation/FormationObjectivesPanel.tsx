import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChevronDown } from "lucide-react";
import { SharkFinLoader } from '@/components/SharkFinLoader';

import { getObjectives, type EmployeeObjective } from "@/api/objectives";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

import {
  fmtDate,
  objectiveStatusBadge,
  objectiveTypeBadge,
} from "./employeeFormationFormatters";

function sortObjectivesByDue(list: EmployeeObjective[]) {
  return [...list].sort((a, b) => {
    if (!a.due_date && !b.due_date) return 0;
    if (!a.due_date) return 1;
    if (!b.due_date) return -1;
    return new Date(a.due_date).getTime() - new Date(b.due_date).getTime();
  });
}

function latestActualFromMilestones(obj: EmployeeObjective): number | null {
  const sorted = [...obj.milestones].sort(
    (m1, m2) => new Date(m1.milestone_date).getTime() - new Date(m2.milestone_date).getTime(),
  );
  for (let i = sorted.length - 1; i >= 0; i -= 1) {
    const v = sorted[i].actual_value;
    if (v != null && !Number.isNaN(Number(v))) return Number(v);
  }
  return null;
}

function isDraftOrCancelled(obj: EmployeeObjective) {
  const s = String(obj.status);
  return s === "draft" || s === "cancelled";
}

function ObjectiveCard({ obj }: { obj: EmployeeObjective }) {
  const isQuant = obj.type === "quantitative";
  const sortedMilestones = [...obj.milestones].sort(
    (a, b) => new Date(a.milestone_date).getTime() - new Date(b.milestone_date).getTime(),
  );
  const chartData = sortedMilestones.map((m) => ({
    label: fmtDate(m.milestone_date),
    attendu: m.expected_value,
    reel: m.actual_value != null ? Number(m.actual_value) : null,
  }));
  const latestActual = latestActualFromMilestones(obj);
  const sortedCheckins = [...obj.checkins].sort(
    (a, b) => new Date(a.checkin_date).getTime() - new Date(b.checkin_date).getTime(),
  );

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <CardTitle className="text-base font-semibold leading-snug">{obj.title}</CardTitle>
            {obj.description?.trim() ? (
              <p className="mt-1 text-sm text-muted-foreground whitespace-pre-wrap">{obj.description}</p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            {objectiveTypeBadge(String(obj.type))}
            {objectiveStatusBadge(String(obj.status))}
          </div>
        </div>
        <CardDescription className="flex flex-wrap gap-x-4 gap-y-1 pt-1">
          {obj.due_date && <span>Échéance : {fmtDate(obj.due_date)}</span>}
          {obj.weight != null && <span>Pondération : {obj.weight}</span>}
          {obj.updated_at && <span>Dernière mise à jour : {fmtDate(obj.updated_at)}</span>}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {isQuant && (
          <div className="space-y-2">
            <p>
              <span className="text-muted-foreground">Valeur cible : </span>
              {obj.kpi_target_value != null
                ? `${obj.kpi_target_value}${obj.kpi_unit ? ` ${obj.kpi_unit}` : ""}`
                : "—"}
              {obj.kpi_label ? ` (${obj.kpi_label})` : ""}
            </p>
            <p>
              <span className="text-muted-foreground">Valeur actuelle (dernier point saisi) : </span>
              {latestActual != null ? `${latestActual}${obj.kpi_unit ? ` ${obj.kpi_unit}` : ""}` : "—"}
            </p>
            {chartData.length > 0 ? (
              <div className="h-56 w-full min-w-0">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="attendu" name="Attendu" stroke="#64748b" dot={false} />
                    <Line type="monotone" dataKey="reel" name="Réel" stroke="#2563eb" connectNulls />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-muted-foreground">Aucun jalon défini pour suivre la courbe attendu / réel.</p>
            )}
          </div>
        )}

        {!isQuant && (
          <div>
            <p className="mb-2 font-medium text-foreground">Suivi qualitatif</p>
            {sortedCheckins.length === 0 ? (
              <p className="text-muted-foreground">Aucun point d&apos;étape enregistré.</p>
            ) : (
              <ul className="space-y-2 border-l-2 border-muted pl-3">
                {sortedCheckins.map((c) => (
                  <li key={c.id} className="text-sm">
                    <span className="text-muted-foreground">{fmtDate(c.checkin_date)}</span>
                    <p className="mt-0.5 whitespace-pre-wrap">{c.progress_note}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {(obj.final_achievement_rate != null || obj.evaluation_comment) && (
          <div className="rounded-md border bg-muted/30 p-3">
            {obj.final_achievement_rate != null && (
              <p>
                <span className="text-muted-foreground">Taux d&apos;atteinte final : </span>
                {obj.final_achievement_rate}%
              </p>
            )}
            {obj.evaluation_comment && (
              <p className="mt-1">
                <span className="text-muted-foreground">Commentaire RH : </span>
                {obj.evaluation_comment}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ObjectivesList({ list }: { list: EmployeeObjective[] }) {
  if (list.length === 0) return null;
  return (
    <div className="space-y-4">
      {list.map((o) => (
        <ObjectiveCard key={o.id} obj={o} />
      ))}
    </div>
  );
}

export function FormationObjectivesPanel({ employeeId }: { employeeId: string }) {
  const currentCalendarYear = new Date().getFullYear();
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyYear, setHistoryYear] = useState(Math.max(currentCalendarYear - 1, 2000));
  const [draftsOpen, setDraftsOpen] = useState(false);

  const pastYears = useMemo(() => {
    const ys: number[] = [];
    for (let y = currentCalendarYear - 1; y >= currentCalendarYear - 15 && y >= 2000; y -= 1) ys.push(y);
    return ys;
  }, [currentCalendarYear]);

  const currentQuery = useQuery({
    queryKey: ["formation-objectives", employeeId, currentCalendarYear],
    queryFn: () =>
      getObjectives({ employee_id: employeeId, period_year: currentCalendarYear, include_inactive: true }),
  });

  const historyQuery = useQuery({
    queryKey: ["formation-objectives", employeeId, "history", historyYear],
    queryFn: () =>
      getObjectives({ employee_id: employeeId, period_year: historyYear, include_inactive: true }),
    enabled: historyOpen,
  });

  const splitObjectives = (list: EmployeeObjective[]) => {
    const main = sortObjectivesByDue(list.filter((o) => !isDraftOrCancelled(o)));
    const drafts = sortObjectivesByDue(list.filter((o) => isDraftOrCancelled(o)));
    return { main, drafts };
  };

  const renderYearBlock = (q: typeof currentQuery, emptyHint: string) => {
    if (q.isLoading) {
      return <SharkFinLoader label="Chargement des objectifs…" />;
    }
    if (q.isError) {
      return <p className="text-sm text-destructive">Impossible de charger vos objectifs.</p>;
    }
    const all = q.data ?? [];
    if (all.length === 0) {
      return <p className="py-6 text-center text-sm text-muted-foreground">{emptyHint}</p>;
    }
    const { main, drafts } = splitObjectives(all);
    return (
      <div className="space-y-4">
        <ObjectivesList list={main} />
        {drafts.length > 0 && (
          <Collapsible open={draftsOpen} onOpenChange={setDraftsOpen}>
            <CollapsibleTrigger asChild>
              <Button variant="ghost" size="sm" className="w-full justify-between sm:w-auto">
                Brouillons et annulés ({drafts.length})
                <ChevronDown className={cn("ml-2 h-4 w-4", draftsOpen && "rotate-180")} />
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-3 space-y-4">
              <ObjectivesList list={drafts} />
            </CollapsibleContent>
          </Collapsible>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Objectifs {currentCalendarYear}</h2>
        <p className="text-sm text-muted-foreground">Vue synthétique en lecture seule.</p>
      </div>
      {renderYearBlock(
        currentQuery,
        `Vos objectifs pour ${currentCalendarYear} seront affichés ici dès qu'ils auront été définis par votre responsable RH.`,
      )}

      {pastYears.length > 0 && (
        <Collapsible open={historyOpen} onOpenChange={setHistoryOpen}>
          <CollapsibleTrigger asChild>
            <Button variant="outline" className="w-full justify-between sm:w-auto">
              Années précédentes
              <ChevronDown className={cn("ml-2 h-4 w-4 transition-transform", historyOpen && "rotate-180")} />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-4 space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm text-muted-foreground">Année</span>
              <Select
                value={String(historyYear)}
                onValueChange={(v) => setHistoryYear(Number.parseInt(v, 10))}
              >
                <SelectTrigger className="w-[140px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {pastYears.map((y) => (
                    <SelectItem key={y} value={String(y)}>
                      {y}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {renderYearBlock(
              historyQuery,
              `Vos objectifs pour ${historyYear} seront affichés ici dès qu'ils auront été définis par votre responsable RH.`,
            )}
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
}

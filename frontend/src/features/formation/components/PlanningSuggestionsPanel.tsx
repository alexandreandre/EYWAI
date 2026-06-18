import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CalendarPlus } from "lucide-react";

import {
  getPlanningSuggestions,
  type PlanningSuggestion,
} from "@/api/annualReviews";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCompany } from "@/contexts/CompanyContext";
import { cn } from "@/lib/utils";

function urgencyBadge(urgency: PlanningSuggestion["urgency"]) {
  if (urgency === "overdue") {
    return (
      <Badge className="bg-red-600 text-white hover:bg-red-600">En retard</Badge>
    );
  }
  return (
    <Badge className="bg-amber-600 text-white hover:bg-amber-600">À planifier</Badge>
  );
}

function planHref(employeeId: string, interviewType: string) {
  return `/employees/${employeeId}?tab=entretiens&planType=${encodeURIComponent(interviewType)}`;
}

export type PlanningSuggestionsPanelProps = {
  compact?: boolean;
  maxRows?: number;
};

export function PlanningSuggestionsPanel({
  compact = false,
  maxRows,
}: PlanningSuggestionsPanelProps) {
  const { activeCompany } = useCompany();
  const year = new Date().getFullYear();

  const { data = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["annual-reviews", "planning-suggestions", activeCompany?.company_id, year],
    queryFn: async () => {
      const res = await getPlanningSuggestions(year);
      return res.data ?? [];
    },
    enabled: Boolean(activeCompany?.company_id),
  });

  const rows = maxRows != null ? data.slice(0, maxRows) : data;

  if (isLoading) {
    return compact ? (
      <Skeleton className="h-16 w-full" />
    ) : (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-64" />
        </CardHeader>
        <CardContent className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (isError) {
    return compact ? null : (
      <Card className="border-destructive/50">
        <CardContent className="flex flex-col gap-2 py-6 text-sm text-destructive">
          <p>Impossible de charger les entretiens annuels à planifier.</p>
          <Button type="button" variant="outline" size="sm" className="w-fit" onClick={() => void refetch()}>
            Réessayer
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (data.length === 0) {
    return compact ? null : (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Entretiens annuels à planifier</CardTitle>
          <CardDescription>
            Cadres et salariés en forfait jour — aucun entretien manquant pour {year}.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (compact) {
    return (
      <ul className="space-y-1 text-sm">
        {rows.map((row) => (
          <li key={`${row.employee_id}-${row.interview_type}`} className="flex items-center justify-between gap-2">
            <span className="truncate">
              {row.employee_name} — {row.interview_type_label}
            </span>
            <Button variant="outline" size="sm" asChild className="shrink-0 h-7 text-xs">
              <Link to={planHref(row.employee_id, row.interview_type)}>Planifier</Link>
            </Button>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Entretiens annuels à planifier</CardTitle>
        <CardDescription>
          Salariés cadres ou en forfait jour sans entretien annuel couvert pour {year}.
          L&apos;entretien de reprise après absence longue durée se planifie manuellement au retour du salarié.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Collaborateur</TableHead>
              <TableHead>Type d&apos;entretien</TableHead>
              <TableHead>Urgence</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={`${row.employee_id}-${row.interview_type}`}>
                <TableCell className="font-medium">{row.employee_name}</TableCell>
                <TableCell>{row.interview_type_label}</TableCell>
                <TableCell>{urgencyBadge(row.urgency)}</TableCell>
                <TableCell className="text-right">
                  <Button variant="outline" size="sm" asChild>
                    <Link to={planHref(row.employee_id, row.interview_type)}>
                      <CalendarPlus className="mr-1.5 h-4 w-4" />
                      Planifier
                    </Link>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {maxRows != null && data.length > maxRows && (
          <p className={cn("mt-3 text-xs text-muted-foreground")}>
            {data.length - maxRows} autre{data.length - maxRows > 1 ? "s" : ""} suggestion
            {data.length - maxRows > 1 ? "s" : ""} — voir l&apos;onglet Obligations légales.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export function usePlanningSuggestionsForPilotage(enabled: boolean) {
  const year = new Date().getFullYear();
  return useQuery({
    queryKey: ["annual-reviews", "planning-suggestions", "pilotage", year],
    queryFn: async () => {
      const res = await getPlanningSuggestions(year);
      return res.data ?? [];
    },
    enabled,
  });
}

export function planningSuggestionPlanHref(row: PlanningSuggestion) {
  return planHref(row.employee_id, row.interview_type);
}

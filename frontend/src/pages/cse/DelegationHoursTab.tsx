// frontend/src/pages/cse/DelegationHoursTab.tsx

import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getDelegationSummary, getDelegationHours, type DelegationSummary } from "@/api/cse";
import { getMonthPeriod } from "@/lib/csePeriod";
import { Plus, Clock, Loader2, ExternalLink, ChevronDown, ChevronRight } from "lucide-react";
import { DelegationHourModal } from "@/components/cse/DelegationHourModal";
import { cn } from "@/lib/utils";

const MONTH_OPTIONS = Array.from({ length: 12 }, (_, i) => ({
  value: String(i),
  label: new Date(2000, i, 1).toLocaleDateString("fr-FR", { month: "long" }),
}));

export default function DelegationHoursTab() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [monthIndex, setMonthIndex] = useState(now.getMonth());
  const [searchTerm, setSearchTerm] = useState("");
  const [hourModalOpen, setHourModalOpen] = useState(false);
  const [expandedEmployeeId, setExpandedEmployeeId] = useState<string | null>(null);

  const { periodStart, periodEnd, label: periodLabel } = getMonthPeriod(year, monthIndex);

  const { data: summary = [], isLoading } = useQuery({
    queryKey: ["cse", "delegation-summary", periodStart, periodEnd],
    queryFn: () => getDelegationSummary(periodStart, periodEnd),
  });

  const { data: detailHours = [], isLoading: loadingDetail } = useQuery({
    queryKey: ["cse", "delegation-hours", expandedEmployeeId, periodStart, periodEnd],
    queryFn: () => getDelegationHours(expandedEmployeeId!, periodStart, periodEnd),
    enabled: !!expandedEmployeeId,
  });

  const filteredSummary = summary.filter((item) => {
    if (!searchTerm) return true;
    const search = searchTerm.toLowerCase();
    return (
      item.first_name.toLowerCase().includes(search) ||
      item.last_name.toLowerCase().includes(search)
    );
  });

  const yearOptions = [now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1];

  const toggleRow = (item: DelegationSummary) => {
    setExpandedEmployeeId((prev) =>
      prev === item.employee_id ? null : item.employee_id,
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-sm font-medium">Période : {periodLabel}</p>
          <Select value={String(monthIndex)} onValueChange={(v) => setMonthIndex(Number(v))}>
            <SelectTrigger className="w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MONTH_OPTIONS.map((m) => (
                <SelectItem key={m.value} value={m.value}>
                  {m.label.charAt(0).toUpperCase() + m.label.slice(1)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
            <SelectTrigger className="w-[100px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {yearOptions.map((y) => (
                <SelectItem key={y} value={String(y)}>
                  {y}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            placeholder="Rechercher un élu…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="max-w-xs"
          />
        </div>
        <Button onClick={() => setHourModalOpen(true)} className="shrink-0">
          <Plus className="h-4 w-4 mr-2" />
          Saisir une heure
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Récapitulatif des heures de délégation
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : filteredSummary.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">Aucun élu sur cette période</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8" />
                  <TableHead>Élu</TableHead>
                  <TableHead>Quota</TableHead>
                  <TableHead>Consommé</TableHead>
                  <TableHead>Restant</TableHead>
                  <TableHead>Progression</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredSummary.map((item) => {
                  const pct =
                    item.quota_hours_per_month > 0
                      ? Math.min(
                          100,
                          (item.consumed_hours / item.quota_hours_per_month) * 100,
                        )
                      : 0;
                  const over = item.remaining_hours < 0;
                  const expanded = expandedEmployeeId === item.employee_id;

                  return (
                    <Fragment key={item.employee_id}>
                      <TableRow
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => toggleRow(item)}
                      >
                        <TableCell>
                          {expanded ? (
                            <ChevronDown className="h-4 w-4" />
                          ) : (
                            <ChevronRight className="h-4 w-4" />
                          )}
                        </TableCell>
                        <TableCell className="font-medium">
                          <Link
                            to={`/employees/${item.employee_id}`}
                            className="inline-flex items-center gap-1 hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {item.first_name} {item.last_name}
                            <ExternalLink className="h-3 w-3 text-muted-foreground" />
                          </Link>
                        </TableCell>
                        <TableCell>{item.quota_hours_per_month} h</TableCell>
                        <TableCell>{item.consumed_hours} h</TableCell>
                        <TableCell>
                          <span className={cn(over && "text-red-600 font-medium")}>
                            {item.remaining_hours} h
                          </span>
                          {over && (
                            <Badge variant="destructive" className="ml-2 text-xs">
                              Dépassement
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell className="min-w-[120px]">
                          <Progress
                            value={pct}
                            className={cn("h-2", over && "[&>div]:bg-destructive")}
                          />
                        </TableCell>
                      </TableRow>
                      {expanded && (
                        <TableRow className="bg-muted/30 hover:bg-muted/30">
                          <TableCell colSpan={6} className="py-3">
                            {loadingDetail ? (
                              <Loader2 className="h-4 w-4 animate-spin mx-auto" />
                            ) : detailHours.length === 0 ? (
                              <p className="text-sm text-muted-foreground text-center">
                                Aucune saisie sur cette période
                              </p>
                            ) : (
                              <ul className="space-y-2 text-sm max-w-2xl mx-auto">
                                {detailHours.map((h) => (
                                  <li
                                    key={h.id}
                                    className="flex flex-wrap justify-between gap-2 border-b pb-2 last:border-0"
                                  >
                                    <span>
                                      {new Date(h.date).toLocaleDateString("fr-FR")} —{" "}
                                      {h.duration_hours} h
                                    </span>
                                    <span className="text-muted-foreground">{h.reason}</span>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {hourModalOpen && (
        <DelegationHourModal open={hourModalOpen} onOpenChange={setHourModalOpen} />
      )}
    </div>
  );
}

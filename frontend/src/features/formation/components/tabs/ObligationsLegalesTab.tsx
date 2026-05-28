// Obligations légales : entretien professionnel 2 ans, bilan 6 ans (Pack Talent T8)

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import apiClient from "@/api/apiClient";
import {
  getAllStatus,
  getEmployeeStatus,
  getOverdueCount,
  saveOverride,
  type LegalObligationOverrideWrite,
  type LegalObligationStatus,
  type ProfessionalInterviewStatus,
} from "@/api/legalObligations";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";
import { useViewOptional } from "@/contexts/ViewContext";
import { isPlatformAdmin } from '@/lib/platformAdmin';

type EmpRow = {
  id: string;
  first_name: string;
  last_name: string;
  email?: string | null;
};

function fmtDate(s?: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("fr-FR");
}

function seniority(hire?: string | null) {
  if (!hire) return "—";
  const a = new Date(hire);
  const b = new Date();
  if (Number.isNaN(a.getTime())) return "—";
  let years = b.getFullYear() - a.getFullYear();
  const m = b.getMonth() - a.getMonth();
  if (m < 0 || (m === 0 && b.getDate() < a.getDate())) years -= 1;
  if (years < 0) return "—";
  if (years === 0) return "Moins d'un an";
  return `${years} an${years > 1 ? "s" : ""}`;
}

function profBadge(st: ProfessionalInterviewStatus) {
  const map: Record<ProfessionalInterviewStatus, { label: string; className: string }> = {
    up_to_date: { label: "À jour", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    due_soon: { label: "Échéance proche", className: "bg-amber-600 text-white hover:bg-amber-600" },
    overdue: { label: "En retard", className: "bg-red-600 text-white hover:bg-red-600" },
    unknown: { label: "Non calculable", className: "bg-muted text-muted-foreground" },
  };
  const x = map[st];
  return <Badge className={x.className}>{x.label}</Badge>;
}

function sixBadge(st: LegalObligationStatus["six_year_review_status"]) {
  const map: Record<
    LegalObligationStatus["six_year_review_status"],
    { label: string; className: string }
  > = {
    validated: { label: "Validé", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    in_progress: { label: "En cours", className: "bg-sky-600 text-white hover:bg-sky-600" },
    not_validated: { label: "Non validé", className: "bg-red-600 text-white hover:bg-red-600" },
    unknown: { label: "Non calculable", className: "bg-muted text-muted-foreground" },
  };
  const x = map[st];
  return <Badge className={x.className}>{x.label}</Badge>;
}

function criteriaSummary(row: LegalObligationStatus) {
  const bits: string[] = [];
  if (row.criteria_training_completed) bits.push("Formation");
  if (row.criteria_certification_obtained) bits.push("Certification");
  if (row.criteria_career_evolution) bits.push("Évolution");
  if (bits.length === 0) return "—";
  return bits.join(", ");
}

export type ObligationsLegalesTabProps = {
  compactTable?: boolean;
};

export default function ObligationsLegalesTab({ compactTable = false }: ObligationsLegalesTabProps = {}) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const viewOpt = useViewOptional();

  const isRh =
    isPlatformAdmin(user) ||
    activeCompany?.role === "admin" ||
    activeCompany?.role === "rh" ||
    activeCompany?.role === "collaborateur_rh";

  const showRhActions = Boolean(
    isRh && !(viewOpt?.isCollaborateurRh && viewOpt.viewMode === "collaborateur"),
  );

  const companyKey = activeCompany?.company_id ?? "none";

  const [filterProf, setFilterProf] = useState<"all" | ProfessionalInterviewStatus>("all");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sheetRow, setSheetRow] = useState<LegalObligationStatus | null>(null);
  const [swTrain, setSwTrain] = useState(false);
  const [swCert, setSwCert] = useState(false);
  const [swCareer, setSwCareer] = useState(false);
  const [notes, setNotes] = useState("");

  const employeesQuery = useQuery({
    queryKey: ["employees", "legal-resolve", companyKey],
    queryFn: async () => {
      const res = await apiClient.get<EmpRow[]>("/api/employees");
      return res.data ?? [];
    },
    enabled: Boolean(activeCompany) && !showRhActions,
  });

  const myEmployeeId = useMemo(() => {
    if (!user?.email || !employeesQuery.data?.length) return null;
    const em = user.email.toLowerCase();
    const hit = employeesQuery.data.find((e) => (e.email || "").toLowerCase() === em);
    return hit?.id ?? null;
  }, [employeesQuery.data, user?.email]);

  const listQuery = useQuery({
    queryKey: ["legal-obligations", "all", companyKey, filterProf],
    queryFn: () => getAllStatus(filterProf === "all" ? undefined : filterProf),
    enabled: Boolean(activeCompany) && showRhActions,
  });

  const overdueQuery = useQuery({
    queryKey: ["legal-obligations", "overdue-count", companyKey],
    queryFn: () => getOverdueCount(),
    enabled: Boolean(activeCompany) && showRhActions,
  });

  const mineQuery = useQuery({
    queryKey: ["legal-obligations", "mine", companyKey, myEmployeeId],
    queryFn: () => getEmployeeStatus(myEmployeeId!),
    enabled: Boolean(activeCompany) && !showRhActions && Boolean(myEmployeeId),
  });

  const saveMut = useMutation({
    mutationFn: async (payload: { employeeId: string; body: LegalObligationOverrideWrite }) =>
      saveOverride(payload.employeeId, payload.body),
    onSuccess: () => {
      toast({ title: "Critères enregistrés" });
      void qc.invalidateQueries({ queryKey: ["legal-obligations"] });
      setSheetOpen(false);
    },
    onError: () => {
      toast({ title: "Erreur", description: "Enregistrement impossible.", variant: "destructive" });
    },
  });

  function openSheet(row: LegalObligationStatus) {
    setSheetRow(row);
    setSwTrain(row.criteria_training_completed);
    setSwCert(row.criteria_certification_obtained);
    setSwCareer(row.criteria_career_evolution);
    setNotes("");
    setSheetOpen(true);
  }

  if (!activeCompany) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          Sélectionnez une entreprise pour afficher les obligations légales.
        </CardContent>
      </Card>
    );
  }

  if (!showRhActions) {
    if (employeesQuery.isLoading || mineQuery.isLoading) {
      return (
        <div className="space-y-4">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      );
    }
    if (employeesQuery.isError || mineQuery.isError) {
      return (
        <Card className="border-destructive/50">
          <CardContent className="flex flex-col gap-3 py-6 text-sm text-destructive">
            <p>Impossible de charger vos obligations légales.</p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="w-fit"
              onClick={() => {
                void employeesQuery.refetch();
                if (myEmployeeId) {
                  void mineQuery.refetch();
                }
              }}
            >
              Réessayer
            </Button>
          </CardContent>
        </Card>
      );
    }
    if (!myEmployeeId) {
      return (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            Aucun profil collaborateur associé à votre compte pour cette entreprise.
          </CardContent>
        </Card>
      );
    }
    const s = mineQuery.data;
    if (!s) {
      return (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            Aucune donnée.
          </CardContent>
        </Card>
      );
    }
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Entretien professionnel (tous les 2 ans)</CardTitle>
            <CardDescription>Statut et prochaine échéance.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">{profBadge(s.professional_interview_status)}</div>
            <p>
              <span className="text-muted-foreground">Prochain entretien dû au : </span>
              {fmtDate(s.professional_interview_next_due)}
            </p>
            {s.last_professional_interview_date && (
              <p className="text-muted-foreground">
                Dernier entretien enregistré : {fmtDate(s.last_professional_interview_date)}
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Bilan de compétences (6 ans)</CardTitle>
            <CardDescription>Critères cumulés sur la période.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">{sixBadge(s.six_year_review_status)}</div>
            <p>
              <span className="text-muted-foreground">Échéance : </span>
              {fmtDate(s.six_year_next_due)}
            </p>
            <p className="text-muted-foreground">Critères : {criteriaSummary(s)}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-muted-foreground">
            {overdueQuery.data != null && overdueQuery.data.count > 0
              ? `${overdueQuery.data.count} collaborateur${overdueQuery.data.count > 1 ? "s" : ""} en retard sur l’entretien professionnel.`
              : "Aucun retard critique sur l’entretien professionnel (vue synthétique)."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Filtrer</span>
          <Select
            value={filterProf}
            onValueChange={(v) => setFilterProf(v as typeof filterProf)}
          >
            <SelectTrigger className="w-[220px]">
              <SelectValue placeholder="Statut entretien" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous</SelectItem>
              <SelectItem value="up_to_date">À jour</SelectItem>
              <SelectItem value="due_soon">Échéance proche</SelectItem>
              <SelectItem value="overdue">En retard</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {listQuery.isLoading && (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      )}

      {listQuery.isError && (
        <Card className="border-destructive/50">
          <CardContent className="flex flex-col gap-3 py-6 text-sm text-destructive">
            <p>Impossible de charger le tableau des obligations.</p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="w-fit"
              onClick={() => void listQuery.refetch()}
            >
              Réessayer
            </Button>
          </CardContent>
        </Card>
      )}

      {!listQuery.isLoading && !listQuery.isError && (listQuery.data?.length ?? 0) === 0 && (
        <Card className="border-dashed">
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Aucun collaborateur actif à afficher.
          </CardContent>
        </Card>
      )}

      {!listQuery.isLoading && (listQuery.data?.length ?? 0) > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Collaborateur</TableHead>
                {!compactTable ? <TableHead>Ancienneté</TableHead> : null}
                <TableHead>Entretien prof.</TableHead>
                <TableHead>Prochaine échéance</TableHead>
                <TableHead>Bilan 6 ans</TableHead>
                {!compactTable ? <TableHead>Critères</TableHead> : null}
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(listQuery.data ?? []).map((row) => (
                <TableRow key={row.employee_id}>
                  <TableCell className="font-medium">{row.employee_name}</TableCell>
                  {!compactTable ? <TableCell>{seniority(row.hire_date)}</TableCell> : null}
                  <TableCell>{profBadge(row.professional_interview_status)}</TableCell>
                  <TableCell>{fmtDate(row.professional_interview_next_due)}</TableCell>
                  <TableCell>{sixBadge(row.six_year_review_status)}</TableCell>
                  {!compactTable ? (
                    <TableCell className="max-w-[200px] text-muted-foreground">
                      {criteriaSummary(row)}
                    </TableCell>
                  ) : null}
                  <TableCell className="text-right">
                    <Button type="button" variant="outline" size="sm" onClick={() => openSheet(row)}>
                      Gérer les critères
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent className="overflow-y-auto sm:max-w-md">
          <SheetHeader>
            <SheetTitle>
              Critères bilan 6 ans — {sheetRow?.employee_name ?? ""}
            </SheetTitle>
          </SheetHeader>
          <div className="mt-6 space-y-6 px-1">
            <p className="text-sm text-muted-foreground">
              Ces critères peuvent être cochés manuellement si le bilan s’est tenu hors EYWAI.
            </p>
            <div className="flex items-center justify-between gap-4">
              <Label htmlFor="lo-train" className="flex-1 cursor-pointer">
                Formation non obligatoire suivie
              </Label>
              <Switch id="lo-train" checked={swTrain} onCheckedChange={setSwTrain} />
            </div>
            <div className="flex items-center justify-between gap-4">
              <Label htmlFor="lo-cert" className="flex-1 cursor-pointer">
                Certification obtenue
              </Label>
              <Switch id="lo-cert" checked={swCert} onCheckedChange={setSwCert} />
            </div>
            <div className="flex items-center justify-between gap-4">
              <Label htmlFor="lo-career" className="flex-1 cursor-pointer">
                Évolution salariale ou professionnelle
              </Label>
              <Switch id="lo-career" checked={swCareer} onCheckedChange={setSwCareer} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="lo-notes">Notes</Label>
              <Textarea
                id="lo-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={4}
                placeholder="Informations utiles pour le suivi…"
              />
            </div>
          </div>
          <SheetFooter className="mt-8">
            <Button
              type="button"
              disabled={!sheetRow || saveMut.isPending}
              onClick={() => {
                if (!sheetRow) return;
                saveMut.mutate({
                  employeeId: sheetRow.employee_id,
                  body: {
                    criteria_training_completed: swTrain,
                    criteria_certification_obtained: swCert,
                    criteria_career_evolution: swCareer,
                    notes: notes.trim() || null,
                  },
                });
              }}
            >
              Enregistrer
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </div>
  );
}

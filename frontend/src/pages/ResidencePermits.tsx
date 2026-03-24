// src/pages/ResidencePermits.tsx
// Page RH : liste et suivi des titres de séjour

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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
import { useToast } from "@/components/ui/use-toast";
import { useCompany } from "@/contexts/CompanyContext";
import { ResidencePermitBadge } from "@/components/ResidencePermitBadge";
import { getResidencePermits } from "@/api/residencePermits";
import type { ResidencePermitListItem, ResidencePermitStatus } from "@/api/residencePermits";
import { Loader2, Search, FileCheck, ChevronRight } from "lucide-react";

const STATUS_ORDER: Record<ResidencePermitStatus | "to_complete", number> = {
  expired: 0,
  to_renew: 1,
  to_complete: 2,
  valid: 3,
};

type FilterStatus = "all" | "expired" | "to_renew" | "to_complete" | "valid";

const FILTER_OPTIONS: { value: FilterStatus; label: string }[] = [
  { value: "all", label: "Tous" },
  { value: "expired", label: "Expirés" },
  { value: "to_renew", label: "À renouveler" },
  { value: "to_complete", label: "À compléter" },
  { value: "valid", label: "Valides" },
];

function sortByUrgency(a: ResidencePermitListItem, b: ResidencePermitListItem): number {
  const statusA = (a.residence_permit_status ?? "to_complete") as keyof typeof STATUS_ORDER;
  const statusB = (b.residence_permit_status ?? "to_complete") as keyof typeof STATUS_ORDER;
  const orderA = STATUS_ORDER[statusA] ?? 4;
  const orderB = STATUS_ORDER[statusB] ?? 4;
  if (orderA !== orderB) return orderA - orderB;
  // Même statut : tri par date d'expiration croissante (null en fin)
  const dateA = a.residence_permit_expiry_date
    ? new Date(a.residence_permit_expiry_date).getTime()
    : Number.MAX_SAFE_INTEGER;
  const dateB = b.residence_permit_expiry_date
    ? new Date(b.residence_permit_expiry_date).getTime()
    : Number.MAX_SAFE_INTEGER;
  return dateA - dateB;
}

function formatExpiryDate(value: string | null): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return value;
  }
}

export default function ResidencePermits() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? "";

  const [filterStatus, setFilterStatus] = useState<FilterStatus>("all");
  const [searchTerm, setSearchTerm] = useState("");

  const {
    data: list = [],
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["residence-permits", activeCompanyId],
    queryFn: async () => {
      const res = await getResidencePermits();
      return res.data;
    },
    enabled: !!activeCompanyId,
  });

  useEffect(() => {
    if (isError) {
      toast({
        title: "Erreur",
        description:
          (error as Error)?.message ?? "Impossible de charger les titres de séjour.",
        variant: "destructive",
      });
    }
  }, [isError, error, toast]);

  const filteredAndSorted = useMemo(() => {
    let items = list;

    if (filterStatus !== "all") {
      items = items.filter((item) => item.residence_permit_status === filterStatus);
    }

    if (searchTerm.trim()) {
      const term = searchTerm.trim().toLowerCase();
      items = items.filter(
        (item) =>
          item.first_name.toLowerCase().includes(term) ||
          item.last_name.toLowerCase().includes(term)
      );
    }

    return [...items].sort(sortByUrgency);
  }, [list, filterStatus, searchTerm]);

  const isEmpty = list.length === 0;
  const noResults = !isEmpty && filteredAndSorted.length === 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Titres de séjour</h1>
        <p className="text-muted-foreground mt-2">
          Suivi des titres de séjour des collaborateurs de l&apos;entreprise
          {activeCompany?.company_name ? ` — ${activeCompany.company_name}` : ""}.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-col sm:flex-row gap-4 items-stretch sm:items-center justify-between">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Rechercher par nom ou prénom..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select
              value={filterStatus}
              onValueChange={(v) => setFilterStatus(v as FilterStatus)}
            >
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder="Filtrer par statut" />
              </SelectTrigger>
              <SelectContent>
                {FILTER_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : isError ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-destructive">
              <p className="font-medium">Erreur de chargement</p>
              <p className="text-sm mt-1 text-muted-foreground">
                {(error as Error)?.message ?? "Impossible de charger les titres de séjour."}
              </p>
            </div>
          ) : isEmpty ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
              <FileCheck className="h-12 w-12 mb-4 opacity-50" />
              <p className="font-medium">Aucun titre de séjour à suivre sur cette entreprise</p>
              <p className="text-sm mt-1">
                Les collaborateurs soumis à un titre de séjour apparaîtront ici après création ou
                modification de leur fiche.
              </p>
            </div>
          ) : noResults ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
              <Search className="h-12 w-12 mb-4 opacity-50" />
              <p className="font-medium">Aucun résultat</p>
              <p className="text-sm mt-1">
                Modifiez le filtre ou la recherche pour afficher des titres de séjour.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[22%]">Collaborateur</TableHead>
                  <TableHead className="w-[20%]">Statut</TableHead>
                  <TableHead className="w-[14%]">Date d&apos;expiration</TableHead>
                  <TableHead className="w-[12%]">Jours restants</TableHead>
                  <TableHead className="w-[14%]">Type</TableHead>
                  <TableHead className="w-[12%]">Numéro</TableHead>
                  <TableHead className="w-[6%]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredAndSorted.map((item) => (
                  <TableRow
                    key={item.employee_id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => navigate(`/employees/${item.employee_id}`)}
                  >
                    <TableCell>
                      <span className="font-medium">
                        {item.first_name} {item.last_name}
                      </span>
                    </TableCell>
                    <TableCell>
                      <ResidencePermitBadge
                        data={{
                          is_subject_to_residence_permit: item.is_subject_to_residence_permit,
                          residence_permit_status: item.residence_permit_status ?? null,
                          residence_permit_expiry_date: item.residence_permit_expiry_date ?? null,
                          residence_permit_days_remaining:
                            item.residence_permit_days_remaining ?? null,
                          residence_permit_data_complete:
                            item.residence_permit_data_complete ?? null,
                        }}
                      />
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatExpiryDate(item.residence_permit_expiry_date)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {item.residence_permit_days_remaining != null
                        ? `${item.residence_permit_days_remaining} jour(s)`
                        : "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {item.residence_permit_type || "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {item.residence_permit_number || "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

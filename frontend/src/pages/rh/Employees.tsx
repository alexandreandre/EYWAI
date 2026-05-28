import { useState, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useQuery } from "@tanstack/react-query";
import { useEmployeesQuery } from "@/hooks/queries/useEmployeesQuery";
import { useActiveCompanyId } from "@/hooks/queries/useCompanyId";
import { queryKeys } from "@/lib/queryKeys";
import { TableSkeleton } from "@/components/skeletons/TableSkeleton";
import { RhPageHeader } from '@/components/layout';
import { PageFetchIndicator } from "@/components/skeletons/PageFetchIndicator";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Search, Landmark } from "lucide-react";
import * as ribAlertsApi from "@/api/ribAlerts";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CreateEmployeeForm } from "@/features/employees/components/CreateEmployeeForm";
import {
  EmployeesTableRow,
  type EmployeeListItem,
} from "@/features/employees/components/EmployeesTableRow";

export default function Employees() {
  const employeesQuery = useEmployeesQuery();
  const companyId = useActiveCompanyId();
  const employees = (employeesQuery.data ?? []) as EmployeeListItem[];
  const loading = employeesQuery.isLoading && !employeesQuery.data;
  const error = employeesQuery.error
    ? "Erreur : Impossible de récupérer la liste des collaborateurs."
    : null;

  const ribAlertsQuery = useQuery({
    queryKey: queryKeys.ribAlerts(companyId),
    queryFn: async () => {
      const res = await ribAlertsApi.getRibAlerts({
        is_read: false,
        is_resolved: false,
        limit: 5,
      });
      return res.data.alerts ?? [];
    },
    enabled: Boolean(companyId),
  });
  const ribAlerts = ribAlertsQuery.data ?? [];
  const [searchTerm, setSearchTerm] = useState("");
  const [employmentStatusFilter, setEmploymentStatusFilter] = useState<string>("actif");

  const navigate = useNavigate();

  const filteredEmployees = employees.filter(emp => {
    const matchesSearch = `${emp.first_name} ${emp.last_name}`.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = employmentStatusFilter === 'all' || (emp.employment_status || 'actif') === employmentStatusFilter;
    return matchesSearch && matchesStatus;
  });

  const tableScrollRef = useRef<HTMLDivElement>(null);
  const virtualizeTable = filteredEmployees.length > 50;
  const rowVirtualizer = useVirtualizer({
    count: filteredEmployees.length,
    getScrollElement: () => tableScrollRef.current,
    estimateSize: () => 73,
    overscan: 8,
  });
  const virtualRows = rowVirtualizer.getVirtualItems();

  return (
    <>
      <PageFetchIndicator isFetching={employeesQuery.isFetching} />
      <div className="space-y-6">
      {ribAlerts.length > 0 && (
        <Card className="border-amber-200 bg-amber-50/50">
          <CardHeader className="py-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Landmark className="h-4 w-4" />
              Alertes RIB ({ribAlerts.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="py-2">
            <ul className="space-y-1 text-sm">
              {ribAlerts.slice(0, 3).map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-2">
                  <span className="text-muted-foreground truncate">{a.title} — {a.message}</span>
                  {a.employee_id && (
                    <Button variant="ghost" size="sm" className="shrink-0 h-7" onClick={() => navigate(`/employees/${a.employee_id}`)}>
                      Fiche
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
      <RhPageHeader
        title="Gestion des Collaborateurs"
        description={loading ? 'Chargement...' : `${employees.length} collaborateurs`}
        actions={<CreateEmployeeForm />}
      />
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4 items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" />
              <Input
                placeholder="Rechercher..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="w-full min-w-0 max-w-[200px]">
              <Select value={employmentStatusFilter} onValueChange={setEmploymentStatusFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="Statut" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tous</SelectItem>
                  <SelectItem value="actif">Actifs</SelectItem>
                  <SelectItem value="en_sortie">En départ</SelectItem>
                  <SelectItem value="parti">Partis</SelectItem>
                  <SelectItem value="archive">Archivés</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Liste des Collaborateurs</CardTitle></CardHeader>
        <CardContent>
          <div
            ref={tableScrollRef}
            className={virtualizeTable ? "max-h-[min(70vh,640px)] overflow-auto" : undefined}
          >
            <Table className="table-fixed">
              <TableHeader
                className={virtualizeTable ? "sticky top-0 z-10 bg-card shadow-sm" : undefined}
              >
                <TableRow>
                  <TableHead className="w-[40%]">Collaborateur</TableHead>
                  <TableHead className="w-[30%]">Poste</TableHead>
                  <TableHead className="w-[25%]">Contrat</TableHead>
                  <TableHead className="w-[5%]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading && (
                  <TableRow>
                    <TableCell colSpan={4} className="py-4">
                      <TableSkeleton rows={6} columns={4} />
                    </TableCell>
                  </TableRow>
                )}
                {error && (
                  <TableRow>
                    <TableCell colSpan={4} className="h-24 text-center text-destructive">
                      {error}
                    </TableCell>
                  </TableRow>
                )}
                {!loading && !error && virtualizeTable && virtualRows.length > 0 && (
                  <TableRow aria-hidden className="border-0 hover:bg-transparent">
                    <TableCell
                      colSpan={4}
                      className="p-0"
                      style={{ height: virtualRows[0].start }}
                    />
                  </TableRow>
                )}
                {!loading &&
                  !error &&
                  (virtualizeTable
                    ? virtualRows.map((virtualRow) => {
                        const employee = filteredEmployees[virtualRow.index];
                        return <EmployeesTableRow key={employee.id} employee={employee} />;
                      })
                    : filteredEmployees.map((employee) => (
                        <EmployeesTableRow key={employee.id} employee={employee} />
                      )))}
                {!loading && !error && virtualizeTable && virtualRows.length > 0 && (
                  <TableRow aria-hidden className="border-0 hover:bg-transparent">
                    <TableCell
                      colSpan={4}
                      className="p-0"
                      style={{
                        height:
                          rowVirtualizer.getTotalSize() -
                          (virtualRows[virtualRows.length - 1]?.end ?? 0),
                      }}
                    />
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
      </div>
    </>
  );
}

import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { useNavigate } from "react-router-dom";
import { MoreHorizontal, Loader2 } from "lucide-react";
import type { AdminCompany } from "@/pages/admin/eywai/companies/types";
import { DEFAULT_PLATFORM_GROUP_NAME } from "@/lib/adminGroup";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type CompaniesTableProps = {
  companies: AdminCompany[];
  majiGroupId: string | null;
  assigningToGroup: boolean;
  onAssignToGroup: (companyId: string) => void;
  onToggleStatus: (company: AdminCompany) => void;
  onDelete: (company: AdminCompany) => void;
  emptyMessage?: string;
};

function formatDate(iso: string): string {
  try {
    return format(new Date(iso), "dd/MM/yyyy", { locale: fr });
  } catch {
    return iso;
  }
}

function isInMajiGroup(company: AdminCompany, majiGroupId: string | null): boolean {
  return Boolean(majiGroupId && company.group_id === majiGroupId);
}

export function CompaniesTable({
  companies,
  majiGroupId,
  assigningToGroup,
  onAssignToGroup,
  onToggleStatus,
  onDelete,
  emptyMessage = "Aucune entreprise.",
}: CompaniesTableProps) {
  const navigate = useNavigate();

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Entreprise</TableHead>
          <TableHead className="hidden md:table-cell">SIRET</TableHead>
          <TableHead>Rattachement</TableHead>
          <TableHead className="hidden sm:table-cell">Employés</TableHead>
          <TableHead className="hidden sm:table-cell">Utilisateurs</TableHead>
          <TableHead>Statut</TableHead>
          <TableHead className="hidden lg:table-cell">Créée le</TableHead>
          <TableHead className="w-[50px]" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {companies.length === 0 ? (
          <TableRow>
            <TableCell colSpan={8} className="py-10 text-center text-muted-foreground">
              {emptyMessage}
            </TableCell>
          </TableRow>
        ) : (
          companies.map((company) => {
            const inGroup = isInMajiGroup(company, majiGroupId);
            return (
              <TableRow key={company.id}>
                <TableCell
                  className="cursor-pointer"
                  onClick={() => navigate(`/super-admin/companies/${company.id}`)}
                >
                  <p className="font-medium">{company.company_name}</p>
                  <p className="text-xs text-muted-foreground">{company.email || "—"}</p>
                </TableCell>
                <TableCell
                  className="hidden md:table-cell text-muted-foreground"
                  onClick={() => navigate(`/super-admin/companies/${company.id}`)}
                >
                  {company.siret || "—"}
                </TableCell>
                <TableCell>
                  {inGroup ? (
                    <Badge variant="secondary">Dans le groupe</Badge>
                  ) : (
                    <div className="flex flex-col gap-1">
                      <Badge variant="outline" className="border-amber-500 text-amber-700">
                        À rattacher
                      </Badge>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 text-xs"
                        disabled={assigningToGroup || !majiGroupId}
                        onClick={() => onAssignToGroup(company.id)}
                      >
                        {assigningToGroup ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          `Rattacher à ${DEFAULT_PLATFORM_GROUP_NAME}`
                        )}
                      </Button>
                    </div>
                  )}
                </TableCell>
                <TableCell
                  className="hidden sm:table-cell tabular-nums"
                  onClick={() => navigate(`/super-admin/companies/${company.id}`)}
                >
                  {company.employees_count ?? 0}
                </TableCell>
                <TableCell
                  className="hidden sm:table-cell tabular-nums"
                  onClick={() => navigate(`/super-admin/companies/${company.id}`)}
                >
                  {company.users_count ?? 0}
                </TableCell>
                <TableCell
                  onClick={() => navigate(`/super-admin/companies/${company.id}`)}
                >
                  <Badge variant={company.is_active ? "default" : "secondary"}>
                    {company.is_active ? "Actif" : "Inactif"}
                  </Badge>
                </TableCell>
                <TableCell
                  className="hidden lg:table-cell text-muted-foreground text-sm"
                  onClick={() => navigate(`/super-admin/companies/${company.id}`)}
                >
                  {formatDate(company.created_at)}
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <MoreHorizontal className="h-4 w-4" />
                        <span className="sr-only">Actions</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() => navigate(`/super-admin/companies/${company.id}`)}
                      >
                        Voir la fiche
                      </DropdownMenuItem>
                      {!inGroup && majiGroupId ? (
                        <DropdownMenuItem onClick={() => onAssignToGroup(company.id)}>
                          Rattacher au groupe
                        </DropdownMenuItem>
                      ) : null}
                      <DropdownMenuItem onClick={() => onToggleStatus(company)}>
                        {company.is_active ? "Désactiver" : "Activer"}
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        className="text-destructive focus:text-destructive"
                        onClick={() => onDelete(company)}
                      >
                        Supprimer définitivement
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}
